# Copyright 2024 CyberWeb Consulting LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''
analyze_gsimg-gem-maps-oldauth.py - AI image processing workflow + Maps

Download image from Google Drive, archive to Google Cloud Storage, send
to Google Cloud Vision for processing, analyze with Gemini LLM, provide
Google Maps link with geolocation data, add results row to Google Sheet.

NOTE: While all other samples are Python 2-3 compatible, the Gemini API
client library does not support 2.x, so this script is only for Python 3.
'''

import argparse
import base64
import io
import os
import sys
import time
import webbrowser

from googleapiclient import discovery, http
from httplib2 import Http
from oauth2client import file, client, tools

from PIL import Image
import google.generativeai as genai
from settings import API_KEY

# gen AI setup
PROMPT: str = 'Describe this image in 2-3 sentences'
MODEL: str = 'gemini-1.5-flash-latest'
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(MODEL)

# constants recommended in settings.py, database, etc., or
# omitted entirely requiring users to enter on command-line
FILE: str =   'YOUR_IMG_ON_DRIVE'
BUCKET: str = 'YOUR_BUCKET_NAME'
FOLDER: str = ''  # YOUR IMG FILE FOLDER (if any)
SHEET: str =  'YOUR_SHEET_ID'
TOP: int = 5  # REQUEST TOP #LABELS FROM CLOUD VISION

# process credentials for OAuth2 tokens
SCOPES: tuple = (
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/devstorage.full_control',
    'https://www.googleapis.com/auth/cloud-vision',
    'https://www.googleapis.com/auth/spreadsheets',
)
store = file.Storage('storage.json')
creds = store.get()
if not creds or creds.invalid:
    _args = sys.argv[1:]
    del sys.argv[1:]
    flow = client.flow_from_clientsecrets('client_secret.json', SCOPES)
    creds = tools.run_flow(flow, store)
    sys.argv.extend(_args)

# create GWS & GCP API service endpoints (Gemini client above, no Maps client)
HTTP = creds.authorize(Http())
DRIVE  = discovery.build('drive',   'v3', http=HTTP)
GCS    = discovery.build('storage', 'v1', http=HTTP)
VISION = discovery.build('vision',  'v1', http=HTTP)  # or API key
SHEETS = discovery.build('sheets',  'v4', http=HTTP)


def k_ize(nbytes: str) -> str:
    'convert bytes to kBs'
    return '%6.2fK' % (nbytes/1000.)


MAPS_API_URL = 'maps.googleapis.com/maps/api/staticmap?size=480x480&markers='
def drive_geoloc_maps(file_id: str) -> str:
    'return Maps API URL if image geolocation found, or empty string otherwise'

    # query file for metadata on Drive, return empty string if no geolocation
    imd = DRIVE.files().get(fileId=file_id,
            fields='imageMediaMetadata').execute().get('imageMediaMetadata')
    if not imd or 'location' not in imd:
        return ''

    # with geolocated image, assemble & return Google Maps Static API call-URL
    return f"{MAPS_API_URL}{imd['location']['latitude']}," \
           f"{imd['location']['longitude']}&key={API_KEY}"


def drive_get_img(fname: str) -> tuple | None:
    'download file from Drive and return file info & binary if found'

    # search for file on Google Drive
    rsp = DRIVE.files().list(q=f"name='{fname}'",
            fields='files(id,name,mimeType,modifiedTime)'
    ).execute().get('files', [])

    # download binary & return file info if found, else return None
    if rsp:
        target = rsp[0]  # use first matching file
        fileId = target['id']
        fname = target['name']
        mtype = target['mimeType']
        binary = DRIVE.files().get_media(fileId=fileId).execute()
        return fname, mtype, target['modifiedTime'], binary, drive_geoloc_maps(fileId)


def gcs_blob_upload(fname: str, bucket: str, media: str, mimetype: str) -> dict:
    'upload an object to a Google Cloud Storage bucket'

    # build blob metadata and upload via GCS API
    body = {'name': fname, 'uploadType': 'multipart', 'contentType': mimetype}
    return GCS.objects().insert(bucket=bucket, body=body,
            media_body=http.MediaIoBaseUpload(io.BytesIO(media), mimetype),
            fields='bucket,name').execute()


def vision_label_img(img: str, top: str) -> str | None:
    'send image to Vision API for label annotation'

    # build image metadata and call Vision API to process
    body = {'requests': [{
                'image':     {'content': img},
                'features': [{'type': 'LABEL_DETECTION', 'maxResults': top}],
    }]}
    rsp = VISION.images().annotate(body=body).execute().get('responses', [{}])[0]

    # return top labels for image as CSV for Sheet (row) else None
    if 'labelAnnotations' in rsp:
        return ', '.join(
                f"({label['score']*100.:.2f}%) {label['description']}" \
                for label in rsp['labelAnnotations'])


def genai_analyze_img(media: str) -> str:
    'analyze image with genAI LLM and return analysis'
    image = Image.open(io.BytesIO(media))
    return model.generate_content((PROMPT, image)).text.strip()


def sheet_append_row(sheet: str, row: str) -> str | None:
    'append row to a Google Sheet, return #cells added else None'

    # call Sheets API to write row to Sheet (via its ID)
    rsp = SHEETS.spreadsheets().values().append(
            spreadsheetId=sheet, range='Sheet1', body={'values': [row]},
            valueInputOption='USER_ENTERED', fields='updates(updatedCells)'
    ).execute()
    if rsp:
        return rsp.get('updates').get('updatedCells')


def main(fname: str, bucket: str, sheet_id: str, folder: str,
         top: str, debug: str) -> bool | None:
    '"main()" drives process from image download through report generation'

    # download img file & info from Drive
    rsp = drive_get_img(fname)
    if not rsp:
        return
    fname, mtype, ftime, data, maps = rsp
    if debug:
        print(f"\n* Downloaded '{fname}' ({mtype}, {ftime}, size: {len(data)}")
        time.sleep(2)

    # upload file to GCS
    gcsname = os.path.join(folder, fname)
    rsp = gcs_blob_upload(gcsname, bucket, data, mtype)
    if not rsp:
        return
    if debug:
        print(f"\n* Uploaded \'{rsp['name']}\' to GCS bucket \'{rsp['bucket']}\''")
        time.sleep(2)

    # process w/Vision
    viz = vision_label_img(base64.b64encode(data).decode('utf-8'), top)
    if not viz:
        return
    if debug:
        print(f'\n* Top {top} labels from Vision API: {viz}')
        time.sleep(2)

    # process w/Gemini
    gem = genai_analyze_img(data)
    if not gem:
        return
    if debug:
        print(f'\n* Analysis from Gemini API: {gem}')
        time.sleep(2)

    # build row to write to Sheet
    fsize = k_ize(len(data))
    row = [folder,
            f'=HYPERLINK("storage.cloud.google.com/{bucket}/{gcsname}", "{fname}")',
            mtype, ftime, fsize, viz, gem
    ]

    # process optional geolocation
    if maps:
        row.append(f'=HYPERLINK("{maps}", "Photo location")')
        if debug:
            print(f'\n* Found location, Maps API URL: {maps}')
            time.sleep(2)

    # add new row to Sheet, get cells-saved count
    rsp = sheet_append_row(sheet_id, row)
    if not rsp:
        return
    if debug:
        print(f'\n* Added {rsp} cells to Google Sheet')
        time.sleep(2)
    return True


if __name__ == '__main__':
    # args: [-hvw] [-i imgfile] [-b bucket] [-f folder] [-s sheet_id] [-t top_labels]
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--imgfile',    default=FILE,
            help=f"image file name (default: '{FILE}')")
    parser.add_argument('-b', '--bucket',     default=BUCKET,
            help=f"Cloud Storage bucket name (default: '{BUCKET}')")
    parser.add_argument('-f', '--folder',     default=FOLDER,
            help=f"Cloud Storage image folder (default: '{FOLDER}')")
    parser.add_argument('-s', '--sheet_id',   default=SHEET,
            help=f"Sheet (Drive file) ID (44-char str; default: '{SHEET}')")
    parser.add_argument('-t', '--top_labels', default=TOP,
            help=f"return top N Vision API labels (default: {TOP})")
    parser.add_argument('-w', '--browser',    action='store_false',
            help='do not open browser to Sheet (default: True [open])')
    parser.add_argument('-v', '--verbose',    action='store_true',
            help='verbose display output (default: False)')
    args = parser.parse_args()

    print(f"Processing file '{args.imgfile}'... please wait")
    print('-' * 65)
    rsp = main(args.imgfile, args.bucket, args.sheet_id,
               args.folder, args.top_labels, args.verbose)
    if rsp:
        if args.browser:
            sheet_url = f'https://docs.google.com/spreadsheets/d/{args.sheet_id}/edit'
            print('\n* DONE: opening web browser to spreadsheet')
            print(sheet_url)
            webbrowser.open(sheet_url, autoraise=True)
        else:
            print('\n* DONE')
    else:
        print(f"\n* ERROR: could not process '{args.imgfile}'")
