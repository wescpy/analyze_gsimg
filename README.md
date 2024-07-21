# AI-enhanced image processing workflow:
### Image archive, analysis, and report generation with Google APIs

| :warning: Original repo likely to be archived |
|:---------------------------|
| Since the original maintainer is no longer at Google, it's highly unlikely anyone there will maintain the repo, so this fork will likely become the canonical version as of 2024. |

In the corresponding [hands-on tutorial](https://codelabs.developers.google.com/codelabs/drive-gcs-vision-sheets?utm_source=codelabs&utm_medium=et&utm_campaign=CDR_wes_workplace_gsdsanalyzegsimg_gsds_200114&utm_content=-) ("codelab"), developers build a command-line Python script the executes an image processing workflow using APIs from [Google Cloud](http://cloud.google.com/apis) (GCP) and [Google Workspace](http://developers.google.com/gsuite) (GWS; formerly G Suite and Google Apps).

The exercise envisions a business scenario helping an enterprise backup their organization's data (image files, for example) to the cloud, analyze that data with machine learning, and report results formatted for management consumption. This repo provides code solutions for each step of the tutorial and also includes alternate versions of the final script which use different security libraries and/or authorization schemes. (More on this below in the "NOTE for GCP Developers" sidebar and [Authorization scheme and alternative versions](#authorization-scheme-and-alternative-versions) section.)

This exercise is for intermediate users. Those new to using Google APIs, specifically GWS and GCP APIs, should complete the introductory codelabs (listed at the bottom) or otherwise gain the requisite skills first. Read more about the app in [this Google Developers blog post](http://goo.gle/3nPxmlc) or [its cross-post to the Google Cloud blog](https://cloud.google.com/blog/topics/developers-practitioners/image-archive-analysis-and-report-generation-google-apis?utm_source=blog&utm_medium=partner&utm_campaign=CDR_wes_workplace_gsdsanalyzegsimg_gsds_200114).


## Prerequisites

- A Google or Gmail account (GWS accounts may require administrator approval)
- A GCP project with an active billing account
- Familiarity with operating system terminal/shell commands
- Basic skills in [Python](http://python.org) (code is 2/3-compatible)
- Experience using Google APIs not required for tutorial but may help when reading the code

| :memo: **NOTE for GCP developers**: |
|:---------------------------|
| The codelab (and code) do not use GCP [*product* client libraries](https://cloud.google.com/apis/docs/cloud-client-libraries) nor _service account_ authorization — instead it uses the lower-level *platform* client libraries (because non-Cloud APIs don't have product libraries yet) and _user account_ authorization (because the target file starts in Google Drive). However, solutions featuring GCP product client libraries as well as service accounts are available as alternatives in the [`alt`](alt) folder. |


## Description

The tutorial has four key objectives... to teach you how to:
1. **Access and download files on Google Drive**
1. **Upload files to Google Cloud Storage**
1. **Analyze images with Google Cloud Vision**
1. **Write rows of data in Google Sheets**

The objectives above are part of a single workflow backing up image files on Drive to GCS, analyzing them with Cloud Vision, and generating a report with the results in Sheets, all by using each product's REST API. (At some point, I'll come up with a Node.js version.) Each step of the tutorial builds successively on the previous, adding one core feature at a time. Each of the `step*` directories represents the working state of the application after successful completion of corresponding tutorial step, culminating with a "clean-up and refactor" step to arrive at the `final` version.

1. **Access & download image from Google Drive**
The first step utilizes the [Drive API](https://developers.google.com/drive) to search for the image file and downloads the first match. Along with the filename and binary payload, the file's MIMEtype, last modification timestamp, and size in bytes are also returned.

1. **Backup image to Cloud Storage**
The next step: upload the image as a "blob" [object](https://cloud.google.com/storage/docs/key-terms#objects) to [Cloud Storage](https://cloud.google.com/storage) (GCS), performing an "insert" to the given [bucket](https://cloud.google.com/storage/docs/key-terms#buckets). One benefit is that data in GCS can also be used by other GCP tools. Also, GCS supports multiple storage classes, whereby the less you access that data, the less it costs, i.e., "the colder, the cheaper." Learn more on the [storage class page](https://cloud.google.com/storage/docs/storage-classes). The script features an optional parent folder `FOLDER` to help organize images in the destination bucket. (The GCP client libraries prep the data for GCS, but this service doesn't exist for when using the lower-level *platform* client library, so we have to employ the latter's [`MediaIoBaseUpload`](https://googleapis.github.io/google-api-python-client/docs/epy/googleapiclient.http.MediaIoBaseUpload-class.html) class to help with the upload.)

1. **Analyze image with Cloud Vision**
The image's binary data is used to send to GCS, but it can be reused with [Cloud Vision](https://cloud.google.com/vision). Use its API to request object detection/identification (called [_label annotation_](https://cloud.google.com/vision/docs/labels)), with the script requesting only the top 5 labels for a faster response. Each label returned includes a confidence score of how likely it appears in the image.

1. **Add results to Google Sheets**
The final feature is report generation in a Google Sheets spreadsheet: for each image backed up, insert a new row of metadata via the [Sheets API](https://developers.google.com/sheets). The row includes:
    1. Any applicable folder
    1. File metadata (name, size, MIMEtype, last modified timestamp)
    1. Link to backed up file on GCS
    1. Cloud Vision labels (image content)

1. **Refactor**
 The final, yet optional, step involves refactoring following best practices, moving the "main" body into a separate function, and adding command-line arguments for user flexibility.

| :memo: Folders do not "exist" on GCS |
|:---------------------------|
| The "/" in GCS filenames is merely a visual cue as folders aren't supported. It may not _feel_ that way as the [Cloud console storage browser](https://console.cloud.google.com/storage/browser) presents a UI (user interface) that follows the abstraction of folders. Regardless, think of folder names as prefixes to help differentiate file objects with the same name. |


## Authorization scheme and alternative versions

We've selected to use *user account authorization* (instead of *service account authorization*), *platform* client libraries (instead of *product* client libraries since those aren't available for Google Workspace (formerly G Suite) APIs), and older auth libraries for readability, consistency, greater Python 2-3 compatibility, and automated OAuth2 token management. This provides what we hope is the least complex user experience. Alternative versions (of the final application) using service accounts, product client libraries, and newer currently-supported auth libraries, are found in the [`alt`](alt) subdirectory. See its [README](alt/README.md) for more information.


## Further study recommendations
Some of you will not do the tutorial, so below are some recommended exercises found in its "Additional Study" section (plus a few bonus ones) as to how you can enhance the script's functionality:

1. (_Images in folders_) Instead of processing one image, let's say you had one or more images in [Google Drive folders](https://developers.google.com/drive/api/v3/search-files). Back them all up matching each Drive folder on GCS.
1. (_Images in ZIP files_) Instead of a folder of images, give the script the ability to process ZIP archives containing image files in a similar way. Consider using the Python [`zipfile` module](http://docs.python.org/library/zipfile).
1. (_Analyze Vision labels_) Cluster similar images together, perhaps start by looking for the most common labels, then the 2nd most common, and so on. You can also use machine learning to do this.
1. (_Create Sheets charts_) Use the Sheets API to [generate charts](https://developers.google.com/sheets/api/samples/charts) based on the Vision API analysis and categorization.
1. (_Process documents instead of images_) Instead of analyzing images with the Vision API, let the data come in the form of PDF files and use the [Cloud Natural Language API](http://cloud.google.com/language) to do the analysis. Process individual documents or use your solutions above to handle PDFs in Drive folders or ZIP archives on Drive.
1. (_Create presentations_) Use the Slides API to generate a slide deck from the backed up images or from the data or charts from the spreadsheet you created/updated with the Sheets API. Check out this pair of blog posts & videos for inspiration: a) [generate slides from spreadsheet data](http://goo.gl/Yb06ZC) and b) [generate slides from images](http://goo.gl/sYL5AM) (JavaScript/Apps Script).
1. (_Export report as PDF_) Enhance the "report generation" part of the tutorial by exporting the Sheet and/or slide deck as PDF, however this isn't a feature of either the Sheets or Slides APIs. **Hint**: Google Drive API. **Extra credit**: merge both the Sheets and Slides PDFs into one master PDF with a tool like Ghostscript (Linux, Windows) or `Combine PDF Pages.action` (macOS).
1. ^(_Enhance reporting with LLMs_) Rather than Cloud Vision labels, ask an LLM (large language model) for a short description of an image, say using the latest OpenAI [GPT](https://platform.openai.com/docs/guides/vision) or Google [Gemini](https://ai.google.dev/gemini-api/docs/api-overview#text_image_input) models via their APIs, and store _that_ in the Sheet.
1. ^(_Local file backup_) Rather than backing up file(s) from Google Drive, implement the ability for users to specify files from their local computer; everything else applies: back up to GCS, analyze with Vision, write to Sheets.
1. ^(_Drive search query_) Rather than specifying specific files to back up, allow the user to enter a search query, and back up all matching files on Drive. **Hint**: Learn about querying Drive on the [search page](https://developers.google.com/drive/api/guides/search-files) in the API docs.
1. ^(_Port to Node.js_) This is more for the maintainer who enjoys exercises like this, but feel free to do it if you're so inclined. :-) As an example, see [this blog post](https://dev.to/googleworkspace/export-google-docs-as-pdf-without-the-docs-api-9o4) on **exporting Google Docs as PDF** with code samples in both Python & Node.js.


## Summary

The tutorial (and its sample app) has a goal of helping developers envision a possible business scenario and show an implementation realizing one possible solution. A secondary goal is showing developers how to use different Google APIs together in a single app. If you find a problem with either the codelab or code in this repo, [check to see if there's already an issue](https://github.com/wescpy/analyze_gsimg/issues) or file a new request otherwise. The SLA (service-level agreement) is "best effort." Also happy to review PRs if you have a fix already.


# References

- Blog posts
    - This tutorial and code: [Google Developers](https://developers.googleblog.com/2020/10/image-archive-analysis-and-report?utm_source=ext&utm_medium=partner&utm_campaign=CDR_wes_workplace_gsdsanalyzegsimg_gsds_200114&utm_content=-) and [Google Cloud](https://cloud.google.com/blog/topics/developers-practitioners/image-archive-analysis-and-report-generation-google-apis?utm_source=blog&utm_medium=partner&utm_campaign=CDR_wes_workplace_gsdsanalyzegsimg_gsds_200114) blog posts
    - [Getting started with GWS APIs and OAuth client IDs](https://dev.to/wescpy/series/25403) (series)
    - [Exporting Google Docs as PDF](https://dev.to/wescpy/export-google-docs-as-pdf-without-the-docs-api-9o4)
    - [A _better_ "Hello World!" Gemini API sample](https://dev.to/wescpy/a-better-google-gemini-api-hello-world-sample-4ddm)
    - [Generating slides from spreadsheet data](http://goo.gl/Yb06ZC)
    - [Generating slides from images](http://goo.gl/sYL5AM) (JS/Google Apps Script)
    - [GWS/G Suite developer overview](http://t.co/XdKEWus0KI) (originally for students)
    - [Accessing GWS/G Suite REST APIs](http://goo.gle/3ateIIQ) (originally for students)
- Google APIs client libraries
    - [Google APIs client library for Python](https://developers.google.com/api-client-library/python)
    - [Google APIs client libraries](https://developers.google.com/api-client-library)
- Google Workspace (GWS)
    - [Google Drive API home page](https://developers.google.com/drive)
    - [Google Sheets API home page](https://developers.google.com/sheets)
    - [Google Workspace (formerly G Suite) developer overview & documentation](https://developers.google.com/gsuite).
- Google Cloud [Platform] (GCP)
    - [Google Cloud Storage home page](https://cloud.google.com/storage)
    - [Google Cloud Vision home page & live demo](https://cloud.google.com/vision)
        - [Cloud Vision API documentation](https://cloud.google.com/vision/docs)
        - [Vision API image labeling docs](https://cloud.google.com/vision/docs/labels)
    - [Python on the Google Cloud Platform](https://cloud.google.com/python)
    - [GCP product client libraries](https://cloud.google.com/apis/docs/cloud-client-libraries)
    - [GCP documentation](https://cloud.google.com/docs)
- Codelabs
    - [Intro to Workspace APIs (Google Drive API)](http://g.co/codelabs/gsuite-apis-intro) (Python)
    - [Using Cloud Vision with Python](http://g.co/codelabs/vision-python) (Python)
    - [Build customized reporting tools (Google Sheets API)](http://g.co/codelabs/sheets) (JS/Node)
    - [Upload objects to Google Cloud Storage](http://codelabs.developers.google.com/codelabs/cloud-upload-objects-to-cloud-storage) (no coding required)

<small>
<sup>^</sup> — bonus exercise not found in the codelab
</small>
