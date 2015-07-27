# Instructions for importing data into DoubleDutch.

## Sponsor Data

1. Get into the regonline_integration Git repository.
2. In the root directory, `source env/bin/activate`
3. `cd utils`
4. `./get_sponsors.py [-r regonline_event_id] -o [output_dir]`

TBD - Need sponsor descriptions.

5. Upload the sponsors.csv file to DoubleDutch.

## Speaker Data

1. Login to:

https://ssl.linklings.net/conferences/ghc/?args=z0Cx0zfsG_aRahTrJUHtGzU30zUAAQbXTrAprcnt3DxGzU30zUAAQbXTtUbb0XfQbGyYt9MNpTHQP0Aprcnt3DxfGbfPCf4fb0HQP0Aprcnt3DxfTEGNND9_TtUbprcnt3DsfGbprcnt3Dsf9aaTzYprcnt3D40QHHGdbUfTtbIXrfGzIXrfNMN2TtIbQtvGQssTzYprcnt3D40bprcnt3DQxGdbUfTzYprcnt3D40Iprcnt3Dxprcnt3DGdbUfTtzIXrfGzIXrfNMNTAprcnt3DxGrU3sCzY0rbprcnt3DybQA0rQyf

2. Nagivate to "Publish", and select the "DoubleDutch" download and
choose "Speakers" from the drop down.

3. Enter: 

http://52.8.24.90/z3rbr4ngy/

In the URL Prefix box.

4. Save the resulting file in some directory, like:

/wintmp/abi/speakers/speakers.csv

5. Download the speaker images from Linklings.  Navigate to
Publish->Proceedings.  In the "Download Submitted Files", select
"Stage 2: Program Material" and Track: "All" - then select each
download file of Moderator Panelist and One Page Summary with zip
(with default filenames).

Skip the "One Page Summary" items.

NOTE: This must be done several times, using the top "Submission Type"
drop down one time for each submission type.

6. Unzip the files from step 5 into a directory, such as:

/wintmp/abi/speaker_images/input/

7. Edit the speakers_csv, indir, and outdir arguments in
speaker_images.py.

8. Copy the image files from speaker_images/output/ to:

cd to the output directory of the script.

rsync -avz * matt@52.8.24.90:/var/www/z3rbr4ngy/

Upload speakers.csv as speakers to DoubleDutch.

## Attendee Data

1. In linkings naviagete to Publish -> Programs, and choose
"Attendees" from the drop down.

2. Enter: 

http://52.8.24.90/z3rbr4ngy/

In the URL Prefix box.

3. Save the resulting file in some directory, like:

/wintmp/abi/speakers/attendee.csv

4. Run:

merge_attendees.py -f /wintmp/abi/speakers/attendee.csv

Upload merged-attendees.csv as attendees to DoubleDutch.



