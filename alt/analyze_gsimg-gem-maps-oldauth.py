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
'''

from __future__ import print_function
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
PROMPT = 'Describe this image in 2-3 sentences'
MODEL = 'gemini-1.5-flash-latest'
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(MODEL)

# constants recommended in settings.py, database, etc., or
# omitted entirely requiring users to enter on command-line
FILE =   'YOUR_IMG_ON_DRIVE'
BUCKET = 'YOUR_BUCKET_NAME'
FOLDER = ''  # YOUR IMG FILE FOLDER (if any)
SHEET =  'YOUR_SHEET_ID'
TOP = 5  # REQUEST TOP #LABELS FROM CLOUD VISION

# process credentials for OAuth2 tokens
SCOPES = (
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


def k_ize(nbytes):
    'convert bytes to kBs'
    return '%6.2fK' % (nbytes/1000.)


MAPS_API_URL = 'https://maps.googleapis.com/maps/api/staticmap?size=480x480&markers='
def drive_geoloc_maps(file_id):
    'return Maps API URL if image geolocation found, or empty string otherwise'

    # query file for metadata on Drive, return empty string if no geolocation
    imd = DRIVE.files().get(fileId=file_id,
            fields='imageMediaMetadata').execute().get('imageMediaMetadata')
    if not imd or 'location' not in imd:
        return ''

    # with geolocated image, assemble & return Google Maps Static API call-URL
    return '%s%s,%s&key=%s' % (MAPS_API_URL, imd['location']['latitude'],
            imd['location']['longitude'], API_KEY)


def drive_get_img(fname):
    'download file from Drive and return file info & binary if found'

    # search for file on Google Drive
    rsp = DRIVE.files().list(q="name='%s'" % fname,
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


def gcs_blob_upload(fname, bucket, media, mimetype):
    'upload an object to a Google Cloud Storage bucket'

    # build blob metadata and upload via GCS API
    body = {'name': fname, 'uploadType': 'multipart', 'contentType': mimetype}
    return GCS.objects().insert(bucket=bucket, body=body,
            media_body=http.MediaIoBaseUpload(io.BytesIO(media), mimetype),
            fields='bucket,name').execute()


def vision_label_img(img, top):
    'send image to Vision API for label annotation'

    # build image metadata and call Vision API to process
    body = {'requests': [{
                'image':     {'content': img},
                'features': [{'type': 'LABEL_DETECTION', 'maxResults': top}],
    }]}
    rsp = VISION.images().annotate(body=body).execute().get('responses', [{}])[0]

    # return top labels for image as CSV for Sheet (row) else None
    if 'labelAnnotations' in rsp:
        return ', '.join('(%.2f%%) %s' % (
                label['score']*100., label['description']) \
                for label in rsp['labelAnnotations'])


def genai_analyze_img(media):
    'analyze image with genAI LLM and return analysis'
    image = Image.open(io.BytesIO(media))
    return model.generate_content((PROMPT, image)).text.strip()


def sheet_append_row(sheet, row):
    'append row to a Google Sheet, return #cells added else None'

    # call Sheets API to write row to Sheet (via its ID)
    rsp = SHEETS.spreadsheets().values().append(
            spreadsheetId=sheet, range='Sheet1', body={'values': [row]},
            valueInputOption='USER_ENTERED', fields='updates(updatedCells)'
    ).execute()
    if rsp:
        return rsp.get('updates').get('updatedCells')


def main(fname, bucket, sheet_id, folder, top, debug):
    '"main()" drives process from image download through report generation'

    # download img file & info from Drive
    rsp = drive_get_img(fname)
    if not rsp:
        return
    fname, mtype, ftime, data, maps = rsp
    if debug:
        print('\n* Downloaded %r (%s, %s, size: %d)' % (fname, mtype, ftime, len(data)))
        time.sleep(2)

    # upload file to GCS
    gcsname = os.path.join(folder, fname)
    rsp = gcs_blob_upload(gcsname, bucket, data, mtype)
    if not rsp:
        return
    if debug:
        print('\n* Uploaded %r to GCS bucket %r' % (rsp['name'], rsp['bucket']))
        time.sleep(2)

    # process w/Vision
    viz = vision_label_img(base64.b64encode(data).decode('utf-8'), top)
    if not viz:
        return
    if debug:
        print('\n* Top %d labels from Vision API: %s' % (top, viz))
        time.sleep(2)

    # process w/Gemini
    gem = genai_analyze_img(data)
    if not gem:
        return
    if debug:
        print('\n* Analysis from Gemini API: %s' % gem)
        time.sleep(2)

    # build row to write to Sheet
    fsize = k_ize(len(data))
    row = [folder,
            '=HYPERLINK("storage.cloud.google.com/%s/%s", "%s")' % (
            bucket, gcsname, fname), mtype, ftime, fsize, viz, gem
    ]

    # process optional geolocation
    if maps:
        row.append('=HYPERLINK("%s", "Photo location")' % maps)
        if debug:
            print('\n* Found location, Maps API URL: %s' % maps)
            time.sleep(2)

    # add new row to Sheet, get cells-saved count
    rsp = sheet_append_row(sheet_id, row)
    if not rsp:
        return
    if debug:
        print('\n* Added %d cells to Google Sheet' % rsp)
        time.sleep(2)
    return True


if __name__ == '__main__':
    # args: [-hv] [-i imgfile] [-b bucket] [-f folder] [-s Sheet ID] [-t top labels]
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--imgfile",   default=FILE,
            help="image file name")
    parser.add_argument("-b", "--bucket_id", default=BUCKET,
            help="Google Cloud Storage bucket name")
    parser.add_argument("-f", "--folder",    default=FOLDER,
            help="Google Cloud Storage image folder (default: '')")
    parser.add_argument("-s", "--sheet_id",  default=SHEET,
            help="Google Sheet (Drive file) ID (44-char str)")
    parser.add_argument("-t", "--viz_top",   default=TOP,
            help="return top N Vision API labels (default: %d)" % TOP)
    parser.add_argument("-v", "--verbose",   action='store_true',
            help="verbose display output (default: False)")
    args = parser.parse_args()

    print('Processing file %r... please wait' % args.imgfile)
    print('-' * 65)
    rsp = main(args.imgfile, args.bucket_id,
            args.sheet_id, args.folder, args.viz_top, args.verbose)
    if rsp:
        sheet_url = 'https://docs.google.com/spreadsheets/d/%s/edit' % args.sheet_id
        print('\n* DONE: opening web browser to spreadsheet')
        print(sheet_url)
        webbrowser.open(sheet_url, new=1, autoraise=True)
    else:
        print('\n* ERROR: could not process %r' % args.imgfile)
