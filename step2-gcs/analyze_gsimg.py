from __future__ import print_function
import io
import mimetypes
import os

from googleapiclient import discovery, http
from httplib2 import Http
from oauth2client import file, client, tools

FNAME = YOUR_IMG_ON_DRIVE
BUCKET = YOUR_BUCKET_NAME
PARENT = ''     # YOUR IMG FILE PREFIX

# process credentials for OAuth2 tokens
SCOPES = (
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/devstorage.full_control',
)
store = file.Storage('storage.json')
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('client_secret.json', SCOPES)
    creds = tools.run_flow(flow, store)

# create API service endpoints
HTTP = creds.authorize(Http())
DRIVE  = discovery.build('drive',   'v3', http=HTTP)
GCS    = discovery.build('storage', 'v1', http=HTTP)


def drive_get_img(fname):
    'download file from Drive and return file info & binary if found'

    # search for file on Google Drive, bail if not found
    rsp = DRIVE.files().list(q="name='%s'" % fname,
            fields='files(id,name,mimeType,modifiedTime)'
    ).execute().get('files', [])

    # else download binary and return file data
    if rsp:
        target = rsp[0]  # use first matching file
        fileId = target['id']
        fname = target['name']
        mtype = target['mimeType']
        return (fname, mtype, target['modifiedTime'],
                DRIVE.files().get_media(fileId=fileId).execute())


def gcs_blob_upload(fname, bucket, media, mimetype):
    'upload an object to a Google Cloud Storage bucket'

    # build blob metadata and upload via GCS API
    body = {'name': fname, 'uploadType': 'multipart',
            'contentType': mimetype}
    return GCS.objects().insert(bucket=bucket, body=body,
            media_body=media, fields='bucket,name').execute()


if __name__ == '__main__':
    # download img file & info from Drive
    rsp = drive_get_img(FNAME)
    if rsp:
        fname, ftype, ftime, data = rsp
        print('Downloaded %r (%s, %s, size: %d)' % (fname, ftype, ftime, len(data)))
        gcsname = '%s/%s'% (PARENT, fname)

        # upload file to GCS
        rsp = gcs_blob_upload(gcsname, BUCKET, http.MediaIoBaseUpload(
                io.BytesIO(data), mimetype=ftype), ftype)
        if rsp:
            print('Uploaded %r to GCS bucket %r' % (rsp['name'], rsp['bucket']))
        else:
            print('ERROR: Cannot upload %r to Cloud Storage' % gcsname)
    else:
        print('ERROR: Cannot download %r from Drive' % fname)
