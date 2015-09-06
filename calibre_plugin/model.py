import datetime
from PyQt5.Qt import Qt, QAbstractTableModel
from calibre.ebooks.metadata.book.base import Metadata
from calibre.web.feeds import feedparser

class OpdsBooksModel(QAbstractTableModel):
    column_headers = [_('Title'), _('Author(s)'), _('Updated')]
    booktableColumnCount = 3
    filterBooksThatAreNewspapers = False
    filterBooksThatAreAlreadyInLibrary = False

    def __init__(self, parent, books = [], db = None):
        QAbstractTableModel.__init__(self, parent)
        self.db = db
        self.books = self.makeMetadataFromParsedOpds(books)
        self.filterBooks()

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Vertical:
            return section + 1
        if section >= len(self.column_headers):
            return None
        return self.column_headers[section]

    def rowCount(self, parent):
        return len(self.filteredBooks)

    def columnCount(self, parent):
        return self.booktableColumnCount

    def data(self, index, role):
        row, col = index.row(), index.column()
        if row >= len(self.filteredBooks):
            return None
        opdsBook = self.filteredBooks[row]
        if role == Qt.UserRole:
            # Return the Metadata object underlying each row
            return opdsBook
        if role != Qt.DisplayRole:
            return None
        if col >= self.booktableColumnCount:
            return None
        if col == 0:
            return opdsBook.title
        if col == 1:
            print "opdsBook.author: %s" % opdsBook.author
            return u' & '.join(opdsBook.author)
        if col == 2:
            return opdsBook.timestamp
        return None

    def downloadOpds(self, opdsUrl):
        feed = feedparser.parse(opdsUrl)
        print feed
        newestUrl = feed.entries[0].links[0].href
        print newestUrl
        newestFeed = feedparser.parse(newestUrl)
        allEntries = newestFeed.entries
        nextUrl = self.findNextUrl(newestFeed.feed)
        while nextUrl is not None:
            nextFeed = feedparser.parse(nextUrl)
            allEntries = allEntries + nextFeed.entries
            nextUrl = self.findNextUrl(nextFeed.feed)
        self.books = self.makeMetadataFromParsedOpds(allEntries)
        self.filterBooks()

    def setFilterBooksThatAreAlreadyInLibrary(self, value):
        if value != self.filterBooksThatAreAlreadyInLibrary:
            self.filterBooksThatAreAlreadyInLibrary = value
            self.filterBooks()

    def setFilterBooksThatAreNewspapers(self, value):
        if value != self.filterBooksThatAreNewspapers:
            self.filterBooksThatAreNewspapers = value
            self.filterBooks()

    def filterBooks(self):
        self.beginResetModel()
        self.filteredBooks = []
        for book in self.books:
            if (not self.isFilteredNews(book)) and (not self.isFilteredAlreadyInLibrary(book)):
                self.filteredBooks.append(book)
        self.endResetModel()

    def isFilteredNews(self, book):
        if self.filterBooksThatAreNewspapers:
            if u'News' in book.tags:
                return True
        return False

    def isFilteredAlreadyInLibrary(self, book):
        if self.filterBooksThatAreAlreadyInLibrary:
            return self.db.has_book(book)
        return False

    def makeMetadataFromParsedOpds(self, books):
        metadatalist = []
        for book in books:
            metadata = self.opdsToMetadata(book)
            metadatalist.append(metadata)
        return metadatalist

    def opdsToMetadata(self, opdsBookStructure):
        authors = opdsBookStructure.author.replace(u'& ', u'&')
        metadata = Metadata(opdsBookStructure.title, authors.split(u'&'))
        metadata.timestamp = datetime.datetime.strptime(opdsBookStructure.updated, '%Y-%m-%dT%H:%M:%S+00:00')
        tags = []
        summary = opdsBookStructure.get(u'summary', u'')
        summarylines = summary.splitlines()
        for summaryline in summarylines:
            if summaryline.startswith(u'TAGS: '):
                tagsline = summaryline.replace(u'TAGS: ', u'')
                tagsline = tagsline.replace(u'<br />',u'')
                tagsline = tagsline.replace(u', ', u',')
                tags = tagsline.split(u',')
        metadata.tags = tags
        bookDownloadUrls = []
        links = opdsBookStructure.get('links', [])
        for link in links:
            url = link.get('href', '')
            bookType = link.get('type', '')
            # Skip covers and thumbnails
            if not bookType.startswith('image/'):
                if bookType == 'application/epub+zip':
                    # EPUB books are preferred and always put at the head of the list if found
                    bookDownloadUrls.insert(0, url)
                else:
                    # Formats other than EPUB (eg. AZW), are appended as they are found
                    bookDownloadUrls.append(url)
        metadata.links = bookDownloadUrls
        return metadata

    def findNextUrl(self, feed):
        for link in feed.links:
            if link.rel == u'next':
                return link.href
        return None
