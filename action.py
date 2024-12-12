#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2015, Steinar Bang ; 2020, un_pogaz <un.pogaz@gmail.com>'


try:
    load_translations()
except NameError:
    pass  # load_translations() added in calibre 1.9

import datetime
import json
import re
from typing import Dict, List, Tuple
from urllib.parse import ParseResult, urlparse

# For Python 3.0 and later
from urllib.request import urlopen

try:
    from qt.core import (
        QAbstractItemView,
        QAbstractTableModel,
        QCheckBox,
        QComboBox,
        QCoreApplication,
        QGridLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QPushButton,
        QSortFilterProxyModel,
        QStringListModel,
        Qt,
        QTableView,
        QToolButton,
    )
    ResizeMode = QHeaderView.ResizeMode
except ImportError:
    from PyQt5.Qt import (
        QAbstractItemView,
        QAbstractTableModel,
        QCheckBox,
        QComboBox,
        QCoreApplication,
        QGridLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QPushButton,
        QSortFilterProxyModel,
        QStringListModel,
        Qt,
        QTableView,
        QToolButton,
    )
    from PyQt5.Qt import QHeaderView as ResizeMode

from calibre.db.cache import Cache
from calibre.ebooks.metadata.book.base import Metadata
from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.widgets2 import Dialog
from calibre.web.feeds import feedparser

from .common_utils import GUI, PLUGIN_NAME, current_db, debug_print, get_icon
from .config import KEY, PLUGIN_ICON, PREFS, TEXT, saveOpdsUrlCombobox


def parse_timestamp(rawTimestamp):
    parsableTimestamp = re.sub(r'((\.\d+)?(\+|-)0\d:00|Z)$', '', rawTimestamp)
    return datetime.datetime.strptime(parsableTimestamp, '%Y-%m-%dT%H:%M:%S')

class DynamicBook(dict):
    pass

class OpdsReaderAction(InterfaceAction):
    
    name = PLUGIN_NAME
    action_spec = (PLUGIN_NAME, None, _('Run the OPDS client UI'), None)
    popup_type = QToolButton.MenuButtonPopup
    action_type = 'current'
    dont_add_to = frozenset(['context-menu-device'])
    
    def genesis(self):
        self.qaction.setIcon(get_icon(PLUGIN_ICON))
        self.qaction.triggered.connect(self.show_dialog)
    
    def show_dialog(self):
        base_plugin_object = self.interface_action_base_plugin
        do_user_config = base_plugin_object.do_user_config
        d = OpdsDialog(self.gui, do_user_config)
        d.show()
    
    def apply_settings(self):
        pass


class OpdsDialog(Dialog):
    def __init__(self, gui, do_user_config):
        self.gui = gui
        self.do_user_config = do_user_config
        
        self.dbAPI = current_db().new_api
        
        Dialog.__init__(self,
            title='OPDS Reader',
            name='plugin.OPDSreader:opds_reader',
            parent=GUI,
        )
    
    def setup_ui(self):
        # The model for the book list
        self.model = OpdsBooksModel(None, [], self.dbAPI)
        self.searchproxymodel = QSortFilterProxyModel(self)
        self.searchproxymodel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.searchproxymodel.setFilterKeyColumn(-1)
        self.searchproxymodel.setSourceModel(self.model)
        
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        
        self.setWindowIcon(get_icon(PLUGIN_ICON))
        
        buttonColumnNumber = 7
        labelColumnWidths = []
        
        # Selection
        self.opdsUrlLabel = QLabel(TEXT.OPDS_URL)
        self.layout.addWidget(self.opdsUrlLabel, 0, 0)
        labelColumnWidths.append(self.layout.itemAtPosition(0, 0).sizeHint().width())
        
        self.opdsUrlEditor = QComboBox(self)
        self.opdsUrlEditor.activated.connect(self.opdsUrlEditorActivated)
        self.opdsUrlEditor.addItems(PREFS[KEY.OPDS_URL])
        self.opdsUrlEditor.setEditable(True)
        self.opdsUrlEditor.setInsertPolicy(QComboBox.InsertAtTop)
        self.layout.addWidget(self.opdsUrlEditor, 0, 1, 1, 3)
        self.opdsUrlLabel.setBuddy(self.opdsUrlEditor)
        
        self.download_opds_button = QPushButton(_('Load OPDS'), self)
        self.download_opds_button.setAutoDefault(False)
        self.download_opds_button.clicked.connect(self.download_opds)
        self.layout.addWidget(self.download_opds_button, 0, buttonColumnNumber)
        
        # Initially download the catalogs found in the root catalog of the URL
        # selected at startup.  Fail quietly on failing to open the URL
        firstCatalogTitle, catalogsList = self.model.downloadOpdsRootCatalog(
            self.gui,
            self.opdsUrlEditor.currentText(),
            False,
        )
        #debug_print(firstCatalogTitle, catalogsList)
        firstCatalogTitle = firstCatalogTitle
        self.currentOpdsCatalogs = catalogsList  # A dictionary of title->feedURL
        
        self.opdsCatalogSelectorLabel = QLabel(_('OPDS Catalog:'))
        self.layout.addWidget(self.opdsCatalogSelectorLabel, 1, 0)
        labelColumnWidths.append(self.layout.itemAtPosition(1, 0).sizeHint().width())
        
        self.opdsCatalogSelector = QComboBox(self)
        self.opdsCatalogSelector.setEditable(False)
        self.opdsCatalogSelectorModel = QStringListModel(self.currentOpdsCatalogs.keys())
        self.opdsCatalogSelector.setModel(self.opdsCatalogSelectorModel)
        self.opdsCatalogSelector.setCurrentText(firstCatalogTitle)
        self.layout.addWidget(self.opdsCatalogSelector, 1, 1, 1, 3)
        
        self.catalog_url_button = QPushButton(_('Catalog to URL'), self)
        self.catalog_url_button.setAutoDefault(False)
        self.catalog_url_button.clicked.connect(self.catalog_to_url)
        self.layout.addWidget(self.catalog_url_button, 1, buttonColumnNumber)
        
        # Search GUI
        self.searchEditor = QLineEdit(self)
        self.searchEditor.returnPressed.connect(self.searchBookList)
        self.layout.addWidget(self.searchEditor, 2, buttonColumnNumber - 2, 1, 2)
        
        # Set the stretch on the search bar (and a minimum width)
        self.layout.setColumnStretch(buttonColumnNumber - 2, 10)
        self.layout.setColumnMinimumWidth(buttonColumnNumber - 2, 200)
        
        self.searchButton = QPushButton(_('Search'), self)
        self.searchButton.setAutoDefault(False)
        self.searchButton.clicked.connect(self.searchBookList)
        self.layout.addWidget(self.searchButton, 2, buttonColumnNumber)
        
        # The main book list
        self.library_view = QTableView(self)
        self.library_view.setSortingEnabled(True)
        self.library_view.setAlternatingRowColors(True)
        self.library_view.setModel(self.searchproxymodel)
        self.library_view.horizontalHeader().setSectionResizeMode(0, ResizeMode.Stretch)
        self.library_view.horizontalHeader().setSectionResizeMode(1, ResizeMode.Stretch)
        self.library_view.horizontalHeader().setSectionResizeMode(2, ResizeMode.ResizeToContents)
        self.library_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.resizeRowHeight()
        self.layout.addWidget(self.library_view, 4, 0, 3, buttonColumnNumber + 1)
        
        # Options GUI
        self.hideBooksAlreadyInLibraryCheckbox = QCheckBox(TEXT.HIDE_BOOK, self)
        self.hideBooksAlreadyInLibraryCheckbox.clicked.connect(self.setHideBooksAlreadyInLibrary)
        self.hideBooksAlreadyInLibraryCheckbox.setChecked(PREFS[KEY.HIDE_BOOK])
        self.layout.addWidget(self.hideBooksAlreadyInLibraryCheckbox, 7, 0, 1, 3)
        
        self.downloadButton = QPushButton(_('Download selected books'), self)
        self.downloadButton.setAutoDefault(False)
        self.downloadButton.clicked.connect(self.downloadSelectedBooks)
        self.layout.addWidget(self.downloadButton, 7, buttonColumnNumber)
        
        self.hideNewsCheckbox = QCheckBox(TEXT.HIDE_NEWSPAPERS, self)
        self.hideNewsCheckbox.clicked.connect(self.setHideNewspapers)
        self.hideNewsCheckbox.setChecked(PREFS[KEY.HIDE_NEWSPAPERS])
        self.layout.addWidget(self.hideNewsCheckbox, 8, 0, 1, 3)
        
        # Let the checkbox initial state control the filtering
        self.model.setFilterBooksThatAreNewspapers(self.hideNewsCheckbox.isChecked())
        self.model.setFilterBooksThatAreAlreadyInLibrary(self.hideBooksAlreadyInLibraryCheckbox.isChecked())
        
        self.fixTimestampButton = QPushButton(_('Fix timestamps of selection'), self)
        self.fixTimestampButton.setAutoDefault(False)
        self.fixTimestampButton.clicked.connect(self.fixBookTimestamps)
        self.layout.addWidget(self.fixTimestampButton, 8, buttonColumnNumber)
        
        self.resize(self.sizeHint())
    
    def resizeRowHeight(self):
        rowHeight = self.library_view.horizontalHeader().height()
        for rowNumber in range(0, self.library_view.model().rowCount()):
            self.library_view.setRowHeight(rowNumber, rowHeight)
        self.library_view.sortByColumn(-1, Qt.AscendingOrder)
    
    def opdsUrlEditorActivated(self, text):
        PREFS[KEY.OPDS_URL] = saveOpdsUrlCombobox(self.opdsUrlEditor)
        firstCatalogTitle, catalogsList = self.model.downloadOpdsRootCatalog(
            self.gui,
            self.opdsUrlEditor.currentText(),
            True,
        )
        self.currentOpdsCatalogs = catalogsList  # A dictionary of title->feedURL
        self.opdsCatalogSelectorModel.setStringList(self.currentOpdsCatalogs.keys())
        self.opdsCatalogSelector.setCurrentText(firstCatalogTitle)
    
    def setHideNewspapers(self, checked):
        PREFS[KEY.HIDE_NEWSPAPERS] = checked
        self.model.setFilterBooksThatAreNewspapers(checked)
    
    def setHideBooksAlreadyInLibrary(self, checked):
        PREFS[KEY.HIDE_BOOK] = checked
        self.model.setFilterBooksThatAreAlreadyInLibrary(checked)
    
    def searchBookList(self):
        searchString = self.searchEditor.text()
        debug_print('Starting book list search for:', searchString)
        self.searchproxymodel.setFilterFixedString(searchString)
    
    def download_opds(self):
        opdsCatalogUrl = self.currentOpdsCatalogs.get(self.opdsCatalogSelector.currentText(), None)
        if not opdsCatalogUrl:
            return
        self.model.downloadOpdsCatalog(self.gui, opdsCatalogUrl)
        if self.model.isCalibreOpdsServer():
            self.model.downloadMetadataUsingCalibreRestApi(self.opdsUrlEditor.currentText())
        self.resizeRowHeight()
    
    def catalog_to_url(self):
        opdsCatalogUrl = self.currentOpdsCatalogs.get(self.opdsCatalogSelector.currentText(), None)
        self.opdsUrlEditor.insertItem(0, opdsCatalogUrl)
        self.opdsUrlEditor.setCurrentIndex(0)
        self.opdsUrlEditorActivated(opdsCatalogUrl)
        self.download_opds()
    
    def config(self):
        self.do_user_config(parent=self)
    
    def downloadSelectedBooks(self):
        selectionmodel = self.library_view.selectionModel()
        if selectionmodel.hasSelection():
            rows = selectionmodel.selectedRows()
            for row in reversed(rows):
                book = row.data(Qt.UserRole)
                self.downloadBook(book)
    
    def downloadBook(self, book):
        if len(book.links) > 0:
            self.gui.download_ebook(book.links[0])
    
    def fixBookTimestamps(self):
        selectionmodel = self.library_view.selectionModel()
        if selectionmodel.hasSelection():
            rows = selectionmodel.selectedRows()
            for row in reversed(rows):
                book = row.data(Qt.UserRole)
                self.fixBookTimestamp(book)
    
    def fixBookTimestamp(self, book):
        bookTimestamp = book.timestamp
        identicalBookIds = self.findIdenticalBooksForBooksWithMultipleAuthors(book)
        bookIdToValMap = {}
        for identicalBookId in identicalBookIds:
            bookIdToValMap[identicalBookId] = bookTimestamp
        if len(bookIdToValMap) < 1:
            debug_print('Failed to set timestamp of book:', book)
        self.dbAPI.set_field('timestamp', bookIdToValMap)
    
    def findIdenticalBooksForBooksWithMultipleAuthors(self, book):
        authorsList = book.authors
        if len(authorsList) < 2:
            return self.dbAPI.find_identical_books(book)
        # Try matching the authors one by one
        identicalBookIds = set()
        for author in authorsList:
            singleAuthorBook = Metadata(book.title, [author])
            singleAuthorIdenticalBookIds = self.dbAPI.find_identical_books(singleAuthorBook)
            identicalBookIds = identicalBookIds.union(singleAuthorIdenticalBookIds)
        return identicalBookIds

class OpdsBooksModel(QAbstractTableModel):
    column_headers = [_('Title'), _('Author(s)'), _('Updated')]
    booktableColumnCount = 3
    filterBooksThatAreNewspapers = False
    filterBooksThatAreAlreadyInLibrary = False
    
    def __init__(self, parent, books = [], db: Cache=None):
        QAbstractTableModel.__init__(self, parent)
        self.dbAPI = db
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
    
    def rowCount(self, parent) -> int:
        return len(self.filteredBooks)
    
    def columnCount(self, parent) -> int:
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
            return ' & '.join(opdsBook.author)
        if col == 2:
            if opdsBook.timestamp is not None:
                return opdsBook.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            return opdsBook.timestamp
        return None
    
    def downloadOpdsRootCatalog(self, gui, opdsUrl, displayDialogOnErrors) -> Tuple[str, Dict]:
        feed = feedparser.parse(opdsUrl)
        if 'bozo_exception' in feed:
            exception = feed['bozo_exception']
            message = _('Failed opening the OPDS URL {:s}:').format(opdsUrl)
            reason = str(getattr(exception, 'reason', ''))
            error_dialog(gui, _('Failed opening the OPDS URL'), message, reason, displayDialogOnErrors)
            return (None, {})
        if 'server' in feed.headers:
            self.serverHeader = feed.headers['server']
        else:
            self.serverHeader = "none"
        debug_print('serverHeader:', self.serverHeader)
        debug_print('feed.entries:', len(feed.entries), [e['title'] for e in feed.entries])
        catalogEntries = {}
        firstTitle = None
        for entry in feed.entries:
            title = entry.get('title', 'No title')
            if firstTitle is None:
                firstTitle = title
            links = entry.get('links', [])
            firstLink = next(iter(links), None)
            if firstLink is not None:
                debug_print(f'firstLink: {title} "{firstLink.href}"')
                catalogEntries[title] = firstLink.href
        return firstTitle, catalogEntries
    
    def downloadOpdsCatalog(self, gui, opdsCatalogUrl):
        debug_print('Downloading catalog:', opdsCatalogUrl)
        opdsCatalogFeed = feedparser.parse(opdsCatalogUrl)
        self.books = self.makeMetadataFromParsedOpds(opdsCatalogFeed.entries)
        self.filterBooks()
        QCoreApplication.processEvents()
        nextUrl = self.findNextUrl(opdsCatalogFeed.feed)
        while nextUrl is not None:
            nextFeed = feedparser.parse(nextUrl)
            self.books = self.books + self.makeMetadataFromParsedOpds(nextFeed.entries)
            self.filterBooks()
            QCoreApplication.processEvents()
            nextUrl = self.findNextUrl(nextFeed.feed)
    
    def isCalibreOpdsServer(self) -> bool:
        return self.serverHeader.startswith('calibre')
    
    def setFilterBooksThatAreAlreadyInLibrary(self, value):
        if value != self.filterBooksThatAreAlreadyInLibrary:
            self.filterBooksThatAreAlreadyInLibrary = value
            self.filterBooks()
    
    def setFilterBooksThatAreNewspapers(self, value):
        if value != self.filterBooksThatAreNewspapers:
            self.filterBooksThatAreNewspapers = value
            self.filterBooks()
    
    def filterBooks(self) -> bool:
        self.beginResetModel()
        self.filteredBooks = []
        for book in self.books:
            if (not self.isFilteredNews(book)) and (not self.isFilteredAlreadyInLibrary(book)):
                self.filteredBooks.append(book)
        self.endResetModel()
    
    def isFilteredNews(self, book) -> bool:
        if self.filterBooksThatAreNewspapers:
            if 'News' in book.tags:
                return True
        return False
    
    def isFilteredAlreadyInLibrary(self, book) -> bool:
        if self.filterBooksThatAreAlreadyInLibrary:
            return self.dbAPI.has_book(book)
        return False
    
    def makeMetadataFromParsedOpds(self, books) -> List[Metadata]:
        metadatalist = []
        for book in books:
            metadata = self.opdsToMetadata(book)
            metadatalist.append(metadata)
        return metadatalist
    
    def opdsToMetadata(self, opdsBookStructure) -> Metadata:
        authors = opdsBookStructure.author.replace('& ', '&') if 'author' in opdsBookStructure else ''
        metadata = Metadata(opdsBookStructure.title, authors.split('&'))
        metadata.uuid = opdsBookStructure.id.replace('urn:uuid:', '', 1) if 'id' in opdsBookStructure else ''
        try:
            rawTimestamp = opdsBookStructure.updated
        except AttributeError:
            rawTimestamp = "1980-01-01T00:00:00+00:00"
        metadata.timestamp = parse_timestamp(rawTimestamp)
        tags = []
        summary = opdsBookStructure.get('summary', '')
        summarylines = summary.splitlines()
        for summaryline in summarylines:
            if summaryline.startswith('TAGS: '):
                tagsline = summaryline.replace('TAGS: ', '')
                tagsline = tagsline.replace('<br />','')
                tagsline = tagsline.replace(', ', ',')
                tags = tagsline.split(',')
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
                    # Formats other than EPUB (like AZW), are appended as they are found
                    bookDownloadUrls.append(url)
        metadata.links = bookDownloadUrls
        return metadata
    
    def findNextUrl(self, feed) -> str:
        for link in feed.links:
            if link.rel == 'next':
                return link.href
        return None
    
    def downloadMetadataUsingCalibreRestApi(self, opdsUrl):
        # The "updated" values on the book metadata, in the OPDS returned
        # by calibre, are unrelated to the books they are returned with:
        # the "updated" value is the same value for all books metadata,
        # and this value is the last modified date of the entire calibre
        # database.
        #
        # It is therefore necessary to use the calibre REST API to get
        # a meaningful timestamp for the books
        
        # Get the base of the web server, from the OPDS URL
        parsedOpdsUrl = urlparse(opdsUrl)
        
        # GET the search URL twice: the first time is to get the total number
        # of books in the other calibre.  The second GET gets arguments
        # to retrieve all book ids in the other calibre.
        parsedCalibreRestSearchUrl = ParseResult(parsedOpdsUrl.scheme, parsedOpdsUrl.netloc, '/ajax/search', '', '', '')
        calibreRestSearchUrl = parsedCalibreRestSearchUrl.geturl()
        calibreRestSearchResponse = urlopen(calibreRestSearchUrl)
        calibreRestSearchJsonResponse = json.load(calibreRestSearchResponse)
        getAllIdsArgument = 'num=' + str(calibreRestSearchJsonResponse['total_num']) + '&offset=0'
        parsedCalibreRestSearchUrl = ParseResult(
            parsedOpdsUrl.scheme,
            parsedOpdsUrl.netloc,
            '/ajax/search',
            '',
            getAllIdsArgument,
            '',
        ).geturl()
        calibreRestSearchResponse = urlopen(parsedCalibreRestSearchUrl)
        calibreRestSearchJsonResponse = json.load(calibreRestSearchResponse)
        bookIds = list(map(str, calibreRestSearchJsonResponse['book_ids']))
        
        # Get the metadata for all books by adding the list of
        # all IDs as a GET argument
        bookIdsGetArgument = 'ids=' + ','.join(bookIds)
        parsedCalibreRestBooksUrl = ParseResult(
            parsedOpdsUrl.scheme,
            parsedOpdsUrl.netloc,
            '/ajax/books',
            '',
            bookIdsGetArgument,
            '',
        )
        calibreRestBooksResponse = urlopen(parsedCalibreRestBooksUrl.geturl())
        booksDictionary = json.load(calibreRestBooksResponse)
        self.updateTimestampInMetadata(bookIds, booksDictionary)
    
    def updateTimestampInMetadata(self, bookIds, booksDictionary):
        bookMetadataById = {}
        for bookId in bookIds:
            bookMetadata = booksDictionary[bookId]
            uuid = bookMetadata['uuid']
            bookMetadataById[uuid] = bookMetadata
        for book in self.books:
            bookMetadata = bookMetadataById[book.uuid]
            rawTimestamp = bookMetadata['timestamp']
            timestamp = parse_timestamp(rawTimestamp)
            book.timestamp = timestamp
        self.filterBooks()
