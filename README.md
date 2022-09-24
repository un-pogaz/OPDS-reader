# Calibre OPDS client

## What's this?

This Calibre plugin is an OPDS client intended to read the contents of a [OPDS Catalogs](https://en.wikipedia.org/wiki/Open_Publication_Distribution_System), and download the referenced book.
It can also be used for download the book from another Calibre installation.

### License
This Calibre plugin is copyright _Steinar Bang_ and _un_pogaz_, 2015-2022, and licensed Under GPL version 3.

See the LICENSE file for more detail.

## How do I use it for download the book from another Calibre installation?

This tool is useful to backup your book collection between two PCs using your home LAN, and that is the procedure documented here:

1. In the Calibre you wish to copy from (in this example called calibre1.home.lan):
    1. Click Preferences
    2. In the "Calibre - Preferences" dialog:
        1. Click "Sharing over the net"
        2. In the "Calibre - Preferences - Sharing over the net" dialog:
            1. Click the "Start Server" button
            2. Select the checkbox "Run server automatically when Calibre starts"
            3. Click the "Apply" button
        3. Click the "close" button
2. In the Calibre you wish to copy to
    1. Install this plugin (see the "How do I install it?" section)
    2. Click the "OPDS client" button
    3. In the "OPDS client" dialog
        1. Edit the "OPDS URL" value, change: http://localhost:8080/opds to: http://calibre1.home.lan:8080/opds and then press the RETURN key on the keyboard
        2. Click the "Download OPDS" button
        3. Wait until the OPDS feed has finished loading (this may take some time if there is a large number of books to load)
            - Note: if no books appear, try unchecking the "Hide books already in the library" checkbox. If that makes a lot of books appear, it means that the two Calibre instances have the same books
        4. select the books you wish to copy into the current Calibre and click the "Download selected books"
            - Calibre will start downloading and installing the books:
            - The Jobs counter in Calibre's lower right corner, will show a decrementing number and the icon will spin
            - The book list will be updated as the books are downloaded
        5. The downloaded books will be in approximately the same order as in the original, but the time stamp will be the download time. To fix the time stamp, click on the "Fixtimestamps of the selection" button
            - The updated timestamps may not show up immediatly, but they will show up after the first update of the display, and the books will be ordered according to the timestamp after stopping and starting Calibre