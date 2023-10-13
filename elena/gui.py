"""
TODO / ideas:
- Fix issue where entire text is sometimes highlighted in yellow.
- Track if data has been changed sice last save (* after filename if
  unsaved)
- Track if editor text has changed (* next to the label)
- Create a backup file when opening a file.
- Move entities in list via drag & drop.
- Edit other items than entities, like header data, decls (??)
- ...
"""
import sys
import os
import re
import uuid
import json

from multiprocessing import freeze_support
from functools import partial

from PyQt6.QtCore import (
    Qt, QObject, QEvent, QAbstractListModel, QModelIndex,
    QItemSelectionModel
)
from PyQt6.QtGui import (
    QIcon, QFontMetricsF, QFontMetrics, QKeySequence, QTextCursor,
    QTextCharFormat, QColor, QPalette, QStandardItem, QAction, QShortcut
)

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenuBar, QMenu, QLabel, QListWidget, QListWidgetItem, QListView, QAbstractItemView,
    QLineEdit, QTextEdit, QPushButton, QCheckBox, QComboBox, QDialog,
    QFileDialog, QMessageBox, QInputDialog, QStyledItemDelegate,
    QFrame
)

from parsers import MapEntitiesParser, EntityParser
from writers import EntityWriter
from models import EntitiesMap
from indexing import EntityListItemIndexer
from helpers import EntityHelper
from oodle import Oodle


class MainWindow(QWidget):
    class EntityListModel(QAbstractListModel):
        """
        Serves as data model for QListView as well as storing all the
        entity data in the items dictionary.
        
        What is actually displayed in the QListView and in what order,
        is determined by displayed_items, which is a list of def_names.
        displayed_items can be changed by insertRows(), removeRows() and
        update_displayed_items().

        The filtered_keys variable is a set of def_names that should
        contain all def_names if no filter is active or a subset
        otherwise. Changing filtered_keys should be followed by calling
        update_displayed_items(), so that the QListView updates the
        list.

        Note on drag & drop: This is totally possible with
        QListView/QListModel, but I haven't managed to get it to work.
        Three methods required for drag & drop have been commented out.
        We'd also have to implement mimeData() and dropMimeData().
        """
        DataKeyRole = Qt.ItemDataRole.UserRole + 1

        def __init__(self, items:dict|None=None) -> None:
            super().__init__()

            self.items = items or {}
            self.displayed_items = []
            self.filtered_keys = set()
            self.init_items()
        
        def init_items(self, items:dict|None=None) -> None:
            self.items = items or self.items
            self.displayed_items = []
            self.filtered_keys = set(self.items.keys())
            self.update_displayed_items()

        def rowCount(self, parent:QModelIndex=QModelIndex()) -> int:
            return len(self.displayed_items)
        
        #def flags(self, index):  # for drag & drop
        #    default_flags = super(MainWindow.EntityListModel, self).flags(index)
        #    return default_flags | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled

        #def supportedDropActions(self):  # for drag & drop
        #    return Qt.DropAction.MoveAction
        
        #def mimeTypes(self):  # for drag & drop
        #    return ['application/elm.row.list']

        def data(self, index:QModelIndex,
                 role:Qt.ItemDataRole=Qt.ItemDataRole.DisplayRole) -> str:
            """
            Important note on this method. Never try to get the full
            item data here, because some weird stuff with Qt will sort
            the keys of the dictionaries before returning them. Instead,
            to get the item data, get the def_name using DataKeyRole,
            then get the item directly form self.items.
            """
            if role == Qt.ItemDataRole.DisplayRole:
                # return what's to be displayed in QListView
                idx = index.row()
                key = self.displayed_items[idx]
                return f'{self.items[key]["def_name"]} ' \
                       f'({self.items[key]["class_name"]})'
            elif role == self.DataKeyRole:
                idx = index.row()
                return self.displayed_items[idx]
        
        def insertRow(self, row:int, new_item:dict,
                      parent:QModelIndex=QModelIndex()) -> bool:
            return self.insertRows(row, 1, new_item)

        def insertRows(self, row:int, count:int, new_items:dict,
                       parent:QModelIndex=QModelIndex()) -> bool:
            """
            We assume that none of the passed items already exists in
            self.items.
            """
            insert_before_def_name = self.get_key_at_displayed_row(row)
            self.beginInsertRows(parent, row, row + count - 1)
            if insert_before_def_name is not None:
                updated_items = {}
                for key, value in self.items.items():
                    i = row
                    if key == insert_before_def_name:
                        for new_key, new_value in new_items.items():
                            updated_items[new_key] = new_value
                            self.displayed_items.insert(i,
                                new_value['def_name'])
                            i += 1
                    updated_items[key] = value
                self.items = updated_items
            else:
                self.items.update(new_items)
                for def_name in new_items:
                    self.displayed_items.append(def_name)
            self.endInsertRows()
            
            return True

        def removeRows(self, row:int, count:int,
                       parent:QModelIndex=QModelIndex()) -> bool:
            self.beginRemoveRows(QModelIndex(), row, row + count - 1)
            for i in range(count):
                self.displayed_items.pop(row + i)
            self.endRemoveRows()

        def remove_item(self, def_name:str) -> None:
            # first, remove from self.items if it exists
            self.items.pop(def_name)
            # if the item is displayed, remove it
            if self.get_row_by_key(def_name) is not None:
                self.removeRows(self.displayed_items.index(def_name), 1)

        def get_key_at_displayed_row(self, row:int) -> str|None:
            try:
                return self.displayed_items[row]
            except Exception as e:
                return None

        def get_row_by_key(self, key:str) -> int|None:
            try:
                return self.displayed_items.index(key)
            except ValueError:
                return None
        
        def get_index_by_key(self, key:str) -> QModelIndex|None:
            row = self.get_row_by_key(key)
            if row is not None:
                return self.index(row)
            return None

        def update_displayed_items(self) -> None:
            self.beginResetModel()
            self.displayed_items = [key for key in self.items if key in
                                    self.filtered_keys]
            self.endResetModel()

    def __init__(self, file_path:str=None) -> None:
        super().__init__()
        self.default_options = {
            'window.basename': 'Elena',
            'font.size': 10,
            'editor.indent': '  ',
            'writer.indent': '  ',
            'stylesheet.invalid_value': 'background-color: mistyrose;'
        }
        self.options = self._load_options()

        self.re_int = re.compile('\d+')
        self.re_int_at_start = re.compile('^([0-9]+) .+$')
        self.re_coords = re.compile(r'(\s*spawnPosition\s*=\s*\{)?\s*x\s*=\s*([\.\-+eE0-9]+)\s*;\s*y\s*=\s*(.+)\s*;\s*z\s*=\s*(.+)\s*;\s*\}?')
        self.re_mat_coords = re.compile(r'mat\[\d+\]\s*=\s*{(.+?)}', re.DOTALL)

        self.file_path = None
        self.map = None
        self.all_defs = set() # set of entityDef names
        self.filter_active = False # use to keep track of filter status
        self.last_selected_item = None # use to keep track of selected items
        self.bookmarks = {} # keep track of bookmarks
        self.bookmarks_filename = 'bookmarks.json'

        self.list_model = self.EntityListModel()
        
        self.parser = MapEntitiesParser()
        self.entity_parser = EntityParser()
        writer_indent = self.options.get('writer.indent', '\t')
        self.writer = EntityWriter(indent=writer_indent)
        self.indexer = EntityListItemIndexer()
        self.helper = EntityHelper()
        self.oodle = Oodle()

        self.bookmarks_window = BookmarksWindow(self.options)
        self._setup_main_window()
        self._install_event_filters()
        self._connect_events()

        if file_path is not None:
            self.open_file(file_path)

    def _load_options(self) -> dict|list|str|int|float|bool|None:
        filename = 'gui_options.json'
        if not os.path.isfile(filename):
            # create the file with default options
            with open(filename, 'w') as f:
                f.write(json.dumps(self.default_options, indent=2))
        
        with open(filename, 'r') as f:
            txt = f.read()
        return json.loads(txt)

    # UI setup ------------------------------------------------------
    def _setup_main_window(self) -> None:
        main_layout = QVBoxLayout() # main layout for entire window
        font = self.font()
        font_size = self.options.get('font.size', 10)
        font.setPointSize(font_size)
        self.setFont(font)

        self.setWindowIcon(QIcon('assets/icon.png'))

        menu_bar = self._setup_menu_bar()
        filter_bar = self._setup_filter_bar()
        left_widget = self._setup_left_widget()
        right_widget = self._setup_right_widget()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        main_layout.addWidget(menu_bar, 0)
        main_layout.addWidget(filter_bar, 0)
        main_layout.addWidget(splitter, 1)

        self.setLayout(main_layout)

        self.setGeometry(0, 100, 900, 600)
        self.update_window_title()

        self.show()

    def _setup_menu_bar(self) -> QMenuBar:
        menu_bar = QMenuBar()

        # file menu
        self.open_file_action = QAction('Open File', self)
        self.open_file_action.setShortcut('Ctrl+O')
        
        self.save_as_action = QAction('Save As...', self)
        self.save_as_action.setShortcut('Ctrl+S')
        
        self.exit_action = QAction('Exit', self)
        self.exit_action.setShortcut('CTRL+Q')

        file_menu = menu_bar.addMenu('File')
        file_menu.addAction(self.open_file_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addAction(self.exit_action)

        # edit menu
        self.fix_arrays_action = QAction(
            'Fix item arrays in editor text', self)

        edit_menu = menu_bar.addMenu('Edit')
        edit_menu.addAction(self.fix_arrays_action)

        # view menu
        self.show_hide_bookmarks_action = QAction(
            'Show/Hide Bookmarks', self)
        view_menu = menu_bar.addMenu('View')
        view_menu.addAction(self.show_hide_bookmarks_action)

        return menu_bar
    
    def _setup_filter_bar(self) -> QWidget:
        # combos
        layers_label = QLabel(text='Layers: ')
        self.layers_combo = CheckableComboBox()
        self.layers_clear_button = QPushButton(text='Clear')
        
        classes_label = QLabel(text='Classes:')
        self.classes_combo = CheckableComboBox()
        self.classes_clear_button = QPushButton(text='Clear')
        
        inherits_label = QLabel(text='Inherits:')
        self.inherits_combo = CheckableComboBox()
        self.inherits_clear_button = QPushButton(text='Clear')
        
        layers_layout = QHBoxLayout()
        layers_layout.addWidget(layers_label, 0)
        layers_layout.addWidget(self.layers_combo, 1)
        layers_layout.addWidget(self.layers_clear_button, 0)

        classes_layout = QHBoxLayout()
        classes_layout.addWidget(classes_label, 0)
        classes_layout.addWidget(self.classes_combo, 1)
        classes_layout.addWidget(self.classes_clear_button, 0)

        inherits_layout = QHBoxLayout()
        inherits_layout.addWidget(inherits_label, 0)
        inherits_layout.addWidget(self.inherits_combo, 1)
        inherits_layout.addWidget(self.inherits_clear_button, 0)

        # position search
        pos_search_label = QLabel(text='Spawn position:')
        self.pos_search_max_distance_edit = QLineEdit()
        self.pos_search_max_distance_edit.setPlaceholderText(
            'Max distance')
        
        self.pos_search_x_edit = QLineEdit()
        self.pos_search_x_edit.setPlaceholderText('x')
        
        self.pos_search_y_edit = QLineEdit()
        self.pos_search_y_edit.setPlaceholderText('y')
        
        self.pos_search_z_edit = QLineEdit()
        self.pos_search_z_edit.setPlaceholderText('z')
        
        pos_search_layout = QHBoxLayout()
        pos_search_layout.addWidget(pos_search_label)
        pos_search_layout.addWidget(self.pos_search_max_distance_edit)
        pos_search_layout.addWidget(self.pos_search_x_edit)
        pos_search_layout.addWidget(self.pos_search_y_edit)
        pos_search_layout.addWidget(self.pos_search_z_edit)

        # key and value search
        key_search_label = QLabel(text='Contains key')
        self.key_search_edit = QLineEdit()
        key_search_exact_match_checkbox_label = QLabel(
            text='Exact match?')
        self.key_search_exact_match_checkbox = QCheckBox()
        
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)

        value_search_label = QLabel(text='Contains value')
        self.value_search_edit = QLineEdit()
        value_search_exact_match_checkbox_label = QLabel(
            text='Exact match?')
        self.value_search_exact_match_checkbox = QCheckBox()

        textsearch_layout = QHBoxLayout()
        textsearch_layout.addWidget(key_search_label)
        textsearch_layout.addWidget(self.key_search_edit)
        textsearch_layout.addWidget(
            key_search_exact_match_checkbox_label)
        textsearch_layout.addWidget(
            self.key_search_exact_match_checkbox)
        textsearch_layout.addWidget(divider)
        textsearch_layout.addWidget(value_search_label)
        textsearch_layout.addWidget(self.value_search_edit)
        textsearch_layout.addWidget(
            value_search_exact_match_checkbox_label)
        textsearch_layout.addWidget(
            self.value_search_exact_match_checkbox)

        # apply filters checkbox
        filters_apply_label = QLabel(text='Apply filters')
        self.filters_apply_checkbox = QCheckBox()

        apply_layout = QHBoxLayout()
        apply_layout.addWidget(filters_apply_label, 0)
        apply_layout.addWidget(self.filters_apply_checkbox, 1)

        # general layout
        filters_layout = QVBoxLayout()
        filters_layout.addLayout(layers_layout)
        filters_layout.addLayout(classes_layout)
        filters_layout.addLayout(inherits_layout)
        filters_layout.addLayout(pos_search_layout)
        filters_layout.addLayout(textsearch_layout)
        filters_layout.addLayout(apply_layout)

        filter_bar = QWidget()
        filter_bar.setLayout(filters_layout)

        return filter_bar

    def _setup_left_widget(self) -> QWidget:
        self.list_label = QLabel(text='Entities list')
        self.list_view = QListView()
        self.list_view.setModel(self.list_model)
        self.list_view.setDragEnabled(True)
        self.list_view.setAcceptDrops(True)
        self.list_view.setDragDropMode(
            QListView.DragDropMode.InternalMove)
        self.list_view.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection)

        left_column = QVBoxLayout()
        left_column.addWidget(self.list_label)
        left_column.addWidget(self.list_view)

        left_widget = QWidget()
        left_widget.setLayout(left_column)

        return left_widget

    def _setup_right_widget(self) -> QWidget:
        self.text_edit_label = QLabel()
        self.text_edit = QTextEdit()
        indent = self.options.get('editor.indent', '  ')
        self.text_edit.setTabStopDistance(
            QFontMetricsF(self.text_edit.font()) \
                .horizontalAdvance(indent))
        
        self.find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)

        self.text_edit_save_button = QPushButton(text='Save')
        self.text_edit_save_button.installEventFilter(self)

        right_column = QVBoxLayout()
        right_column.addWidget(self.text_edit_label)
        right_column.addWidget(self.text_edit)
        right_column.addWidget(self.text_edit_save_button)

        right_widget = QWidget()
        right_widget.setLayout(right_column)

        return right_widget
    
    def _install_event_filters(self) -> None:
        # combos
        self.layers_clear_button.installEventFilter(self)
        self.classes_clear_button.installEventFilter(self)
        self.inherits_clear_button.installEventFilter(self)

        # position search
        self.pos_search_max_distance_edit.installEventFilter(self)
        self.pos_search_x_edit.installEventFilter(self)
        self.pos_search_y_edit.installEventFilter(self)
        self.pos_search_z_edit.installEventFilter(self)

        # list view
        self.list_view.installEventFilter(self)
    
    def _connect_events(self) -> None:
        # menu action events
        self.open_file_action.triggered.connect(
            self.on_open_file_action)
        self.save_as_action.triggered.connect(self.on_save_as_action)
        self.exit_action.triggered.connect(self.close)
        self.fix_arrays_action.triggered.connect(
            self.fix_item_arrays_in_editor)
        self.show_hide_bookmarks_action.triggered.connect(
            self.on_show_hide_bookmarks_action)

        # combo events
        self.layers_combo.model().dataChanged.connect(
            self.apply_filters)
        self.classes_combo.model().dataChanged.connect(
            self.apply_filters)
        self.inherits_combo.model().dataChanged.connect(
            self.apply_filters)

        # position events
        self.pos_search_max_distance_edit.textEdited.connect(
            self.on_pos_search_text_edited)
        self.pos_search_x_edit.textEdited.connect(
            self.on_pos_search_text_edited)
        self.pos_search_y_edit.textEdited.connect(
            self.on_pos_search_text_edited)
        self.pos_search_z_edit.textEdited.connect(
            self.on_pos_search_text_edited)

        # key and value events
        self.key_search_edit.returnPressed.connect(
            self.apply_filters)
        self.key_search_exact_match_checkbox.stateChanged.connect(
            self.apply_filters)
        self.value_search_edit.returnPressed.connect(
            self.apply_filters)
        self.value_search_exact_match_checkbox.stateChanged.connect(
            self.apply_filters)

        # apply filters checkbox events
        self.filters_apply_checkbox.stateChanged.connect(
            self.apply_filters)

        # list view events
        self.list_view.selectionModel().currentChanged.connect(
            self.on_list_view_changed)

        # find_shortcut events
        self.find_shortcut.activated.connect(self.on_find_shortcut)

        # bookmark events
        self.bookmarks_window.bookmark_list.itemDoubleClicked.connect(
            self.bookmark_item_double_clicked)

    # data handling -------------------------------------------------
    def data_item_from_entity(self, entity:dict) -> dict:
        def_name = self.helper.get_def_name(entity)
        class_name = self.helper.get_class(entity)
        inherit = self.helper.get_inherit(entity)

        return {
            def_name: {
                'def_name': def_name,  # this is for convenience
                'class_name': class_name,
                'inherit': inherit,
                'entity': entity
            }
        }
    
    def init_data(self) -> None:
        """
        Initial data preparation. Should only be called when a new file
        is opened.

        EntitiesMap.entities stores a list of dicts, where each item
        represents an entity. However, we need to reference the entity
        by def name, so we have to convert the data structure to a dict
        first.

        This means duplicate entity def names are not supported.
        """
        items = {}
        for entity in self.map.entities:
            self.all_defs.add(self.helper.get_def_name(entity))
            item = self.data_item_from_entity(entity)
            items.update(item)
        self.list_model.init_items(items)
        self.indexer.intialize_indices()
        self.indexer.index(self.list_model.items)
        self.update_combo_filters()

    def apply_filters(self) -> None:
        if self.filters_apply_checkbox.isChecked():
            selected_layers = set(self.layers_combo.currentData())
            selected_classes = set(self.classes_combo.currentData())
            selected_inherits = set(self.inherits_combo.currentData())

            # search by layers
            if len(selected_layers) > 0:
                layer_defs = set()
                if 'No layers' in selected_layers:
                    layer_defs.update(
                        self.indexer.get_entities_without_layers())
                for layer in selected_layers:
                    layer_defs.update(self.indexer.find_layer(layer))
            else:
                layer_defs = set(self.all_defs)
            
            # search by classes
            if len(selected_classes) > 0:
                class_defs = set()
                for def_class in selected_classes:
                    class_defs.update(
                        self.indexer.find_class(def_class))
            else:
                class_defs = set(self.all_defs)
            
            # search by inherits
            if len(selected_inherits) > 0:
                inherit_defs = set()
                for inherit in selected_inherits:
                    inherit_defs.update(
                        self.indexer.find_inherit(inherit))
            else:
                inherit_defs = set(self.all_defs)
            
            # search by spawn position distance
            if self.pos_search_fields_valid():
                x = float(self.pos_search_x_edit.text())
                y = float(self.pos_search_y_edit.text())
                z = float(self.pos_search_z_edit.text())
                pos_str = f'{x}x{y}x{z}'
                max_distance = float(
                    self.pos_search_max_distance_edit.text())
                pos_defs = set(
                    self.indexer.find_surrounding_spawn_positions(
                        pos_str, max_distance)
                )
            else:
                pos_defs = set(self.all_defs)

            # search by key
            partial_match = \
                not self.key_search_exact_match_checkbox.isChecked()
            key_search = self.key_search_edit.text()
            if len(key_search) > 0:
                key_defs = set(self.indexer.find_key(
                    key_search, partial=partial_match))
            else:
                key_defs = set(self.all_defs)
            
            # search by value
            partial_match = \
                not self.value_search_exact_match_checkbox.isChecked()
            value_search = self.value_search_edit.text()
            if len(value_search) > 0:
                value_defs = set(self.indexer.find_value(value_search,
                    partial=partial_match))
            else:
                value_defs = set(self.all_defs)
            

            self.list_model.filtered_keys = (layer_defs & class_defs &
                                             inherit_defs & pos_defs &
                                             key_defs & value_defs)
            self.filter_active = True
        else:
            self.list_model.filtered_keys = set(self.all_defs)
            self.filter_active = False
        self.list_model.update_displayed_items()
        
        # jump to last selected item
        self.restore_last_selection()

    # event and filter callbacks ------------------------------------
    def eventFilter(self, src:QObject, e:QEvent) -> bool:
        """
        Overwrites the eventFilter method. This is a catchall function
        for low level events emitted by objects that have added this
        method using the .installEventFilter method.
        """
        btn_release = QEvent.Type.MouseButtonRelease
        left_button = Qt.MouseButton.LeftButton
        
        if e.type() == btn_release and e.button() == left_button:
            if src == self.layers_clear_button:
                self.layers_combo.uncheckAll()
                self.apply_filters()
            elif src == self.classes_clear_button:
                self.classes_combo.uncheckAll()
                self.apply_filters()
            elif src == self.inherits_clear_button:
                self.inherits_combo.uncheckAll()
                self.apply_filters()
            elif src == self.text_edit_save_button:
                self.save_current_entity()
        elif src == self.list_view:
            if e.type() == QEvent.Type.ContextMenu:
                self.show_list_context_menu(e)
        elif e.type() == QEvent.Type.KeyPress and \
                src in [self.pos_search_max_distance_edit,
                        self.pos_search_x_edit,
                        self.pos_search_y_edit,
                        self.pos_search_z_edit]:
            key = e.key()
            k_esc = Qt.Key.Key_Escape
            k_enter = Qt.Key.Key_Enter
            k_return = Qt.Key.Key_Return
            
            if key == k_esc:
                self.clear_pos_coord_filters()
                self.validate_search_fields()
                return True
            elif key == k_enter or key == k_return:
                self.apply_filters()
                return True
        
        return super().eventFilter(src, e)

    def closeEvent(self, event):
        """
        Called in case the user clicks on the close window icon, presses
        ALT+F4 or if self.close was called via File -> Exit action or CTRL+Q.
        """
        self._save_bookmarks()
        self.bookmarks_window.close()
        event.accept()

    def on_open_file_action(self) -> None:
        self._save_bookmarks()
        self.file_path, _ = \
            QFileDialog.getOpenFileName(self, "Open file",
                "", "Map Entities Files (*.entities);;All Files (*)")
        if self.file_path != '':
            self.open_file(self.file_path)
    
    def on_save_as_action(self) -> None:
        if self.map is None:
            return
        dialog = CustomSaveFileDialog(self, "Save File", "",
            "Map Entities Files (*.entities);;All Files (*)")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            file_path = dialog.selectedFiles()[0]
            compress = dialog.compress_checkbox.isChecked()
            if file_path:
                if os.path.isfile(file_path):
                    reply = QMessageBox.question(self,
                        'Overwrite File?', 
                        "The file already exists. Are you sure?", 
                        QMessageBox.StandardButton.Ok |
                        QMessageBox.StandardButton.Cancel)

                    if reply == QMessageBox.StandardButton.Ok:
                        self.save_file(file_path, compress)
                else:
                    self.save_file(file_path, compress)

    def on_show_hide_bookmarks_action(self) -> None:
        if self.bookmarks_window.isVisible():
            self.bookmarks_window.hide()
        else:
            self.bookmarks_window.show()

    def on_pos_search_text_edited(self, txt:str) -> None:
        txt = self.re_mat_coords.sub('', txt).strip()
        if match := self.re_coords.search(txt):
            self.pos_search_x_edit.setText(match.group(2))
            self.pos_search_y_edit.setText(match.group(3))
            self.pos_search_z_edit.setText(match.group(4))
        
        self.validate_search_fields()

    def on_list_view_changed(self, current:QModelIndex,
                             previous:QModelIndex) -> None:
        def_name = current.data(self.list_model.DataKeyRole)
        if def_name is None:
            return
        
        self.last_selected_item = def_name
        item = self.list_model.items[def_name]
        entity_txt = self.writer.entities_to_str([item['entity']])
        self.text_edit_label.setText(item['def_name'])
        self.text_edit.setText(entity_txt)
        self.reset_highlight()

        if self.filters_apply_checkbox.isChecked() and \
                self.value_search_edit.text().strip() != '':
            keyword = self.value_search_edit.text()
            self.highlight_text(keyword)
    
    def on_find_shortcut(self) -> None:
        find_text, ok = QInputDialog.getText(self, "Find Text",
                                             "Text to find:")
        if ok:
            self.reset_highlight()
            text_cursor = self.text_edit.textCursor()
            found_cursor = self.text_edit.document().find(find_text,
                                                          text_cursor)
            
            if not found_cursor.isNull():
                self.text_edit.setTextCursor(found_cursor)
                self.highlight_text(find_text)
            else:
                QMessageBox.information(self, "Find",
                                        "No more occurrences found.")
    
    def bookmark_item_double_clicked(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        index = self.list_model.get_index_by_key(key)
        if index is not None:
            self.list_view.selectionModel().select(
                index, QItemSelectionModel.SelectionFlag.Select)
            self.list_view.scrollTo(
                index, QAbstractItemView.ScrollHint.PositionAtCenter)

    # validation methods --------------------------------------------
    def pos_search_fields_valid(self) -> bool:
        pos_x_edit = self.pos_search_x_edit
        pos_y_edit = self.pos_search_y_edit
        pos_z_edit = self.pos_search_z_edit
        pos_distance_edit = self.pos_search_max_distance_edit
        
        for line_field in [pos_x_edit, pos_y_edit, pos_z_edit,
                           pos_distance_edit]:
            txt = line_field.text()
            if not self.is_float(txt):
                return False
        return True
    
    def validate_search_fields(self) -> bool:
        pos_x_edit = self.pos_search_x_edit
        pos_y_edit = self.pos_search_y_edit
        pos_z_edit = self.pos_search_z_edit
        pos_distance_edit = self.pos_search_max_distance_edit
        x_y_z_valid = True
        distance_valid = True

        stylesheet_invalid_value = \
            self.options.get('stylesheet.invalid_value', '')

        for line_field in [pos_x_edit, pos_y_edit, pos_z_edit]:
            txt = line_field.text()
            if txt == '' or self.is_float(txt):
                line_field.setStyleSheet('')
            else:
                x_y_z_valid = False
                line_field.setStyleSheet(stylesheet_invalid_value)
        txt = pos_distance_edit.text()
        if txt == '' or self.is_float(txt):
            pos_distance_edit.setStyleSheet('')
        else:
            distance_valid = False
            pos_distance_edit.setStyleSheet(stylesheet_invalid_value)
        
        return x_y_z_valid and distance_valid

    # general actions -----------------------------------------------
    def open_file(self, file_path:str) -> None:
        dialog_title = 'Loading'
        dialog_msg = 'Please wait a few seconds, loading file...'
        dialog = self.create_dialog(dialog_title, dialog_msg)
        try:
            if self.oodle.is_compressed(file_path):
                data = self.oodle.decompress(file_path)
            else:
                with open(file_path, 'r') as f:
                    data = f.read()
            self.map = self.parser.parse(data)
            self.file_path = file_path
            self.text_edit.clear()
            self.text_edit_label.setText('')
            self.init_data()
            self._load_bookmarks()
            self.update_window_title()
        except Exception as e:
            self.error_modal('Error parsing file', e)
        finally:
            dialog.close()
    
    def save_file(self, file_path:str, compress:bool) -> None:
        try:
            # convert dict entities back to list form for the writer
            entities = []
            for _, values in self.list_model.items.items():
                entities.append(values['entity'])
            self.map.entities = entities
            self.writer.write_to_file(self.map, file_path)
            if compress:
                self.oodle.compress_to_file(file_path, file_path)
            self.file_path = file_path
            self._save_bookmarks()
            self.info_modal('File saved', 'The file was saved')
            self.update_window_title()
        except Exception as e:
            msg = f'Error while writing the file: {str(e)}'
            self.error_modal('Error writing file', msg)
    
    def _load_bookmarks(self):
        self.bookmarks_window.bookmark_list.clear()
        if os.path.isfile(self.bookmarks_filename):
            with open(self.bookmarks_filename, 'r') as f:
                self.bookmarks = json.load(f)
            open_filename = os.path.split(self.file_path)[1]
            if open_filename in self.bookmarks:
                for key, value in self.bookmarks[open_filename].items():
                    item = QListWidgetItem()
                    item.setText(key)
                    item.setData(Qt.ItemDataRole.UserRole, value)
                    self.bookmarks_window.bookmark_list.addItem(item)
        else:
            self._save_bookmarks()

    def _save_bookmarks(self):
        if self.file_path is None:
            return
        
        open_filename = os.path.split(self.file_path)[1]
        self.bookmarks[open_filename] = {}
        for i in range(self.bookmarks_window.bookmark_list.count()):
            item = self.bookmarks_window.bookmark_list.item(i)
            key = item.text()
            value = item.data(Qt.ItemDataRole.UserRole)
            self.bookmarks[open_filename][key] = value
        with open(self.bookmarks_filename, 'w') as f:
            json.dump(self.bookmarks, f)

    def update_window_title(self) -> None:
        window_basename = self.options.get('window.basename',
            'window.basename not defined')
        if self.file_path is not None:
            self.setWindowTitle(window_basename + ': ' + \
                                os.path.split(self.file_path)[1])
        else:
            self.setWindowTitle(window_basename)

    # filter actions ------------------------------------------------
    def clear_combo_filters(self) -> None:
        self.layers_combo.clear()
        self.classes_combo.clear()
        self.inherits_combo.clear()

    def update_combo_filters(self) -> None:
        self.clear_combo_filters()
        
        unique_layers = self.indexer.get_unique_layers()
        unique_classes = self.indexer.get_unique_classes()
        unique_inherits = self.indexer.get_unique_inherits()
        self.layers_combo.addItem('No layers')
        self.layers_combo.addItems(sorted(unique_layers))
        self.layers_combo.setText('')
        self.classes_combo.addItems(sorted(unique_classes))
        self.classes_combo.setText('')
        self.inherits_combo.addItems(sorted(unique_inherits))
        self.inherits_combo.setText('')

    # entity list actions -------------------------------------------
    def restore_last_selection(self):
        if self.last_selected_item:
            index = self.list_model.get_index_by_key(
                self.last_selected_item)
            if index is not None:
                self.list_view.selectionModel().select(
                    index, QItemSelectionModel.SelectionFlag.Select)
                self.list_view.scrollTo(
                    index, QAbstractItemView.ScrollHint.PositionAtCenter)

    def show_list_context_menu(self, event:QEvent) -> None:
        index = self.list_view.indexAt(event.pos())
        if index.isValid():
            menu = QMenu(self)
            bookmark_action = QAction('Bookmark', self)
            bookmark_action.triggered.connect(
                partial(self.bookmark_current_item, index))
            add_entity_action = QAction("Add new entity above", self)
            add_entity_action.triggered.connect(
                partial(self.create_new_entity, index))
            insert_entities_action = QAction(
                "Insert entities above from file", self)
            insert_entities_action.triggered.connect(
                partial(self.insert_entities_from_file, index))
            export_entities_action = QAction(
                "Export selected entities to file", self)
            export_entities_action.triggered.connect(
                self.export_selection)
            remove_entities_action = QAction("Remove selected entities",
                                             self)
            remove_entities_action.triggered.connect(
                self.remove_selected_entities)
            
            menu.addAction(bookmark_action)
            menu.addAction(add_entity_action)
            menu.addAction(insert_entities_action)
            menu.addAction(export_entities_action)
            menu.addAction(remove_entities_action)
            menu.exec(event.globalPos())

    def bookmark_current_item(self, index:QModelIndex):
        def_name = index.data(self.list_model.DataKeyRole)
        dialog = BookmarkNameDialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            bm_name = dialog.line_edit.text()
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, def_name)
            item.setText(bm_name)
            self.bookmarks_window.bookmark_list.addItem(item)

    def create_new_entity(self, index:QModelIndex) -> None:
        def_name = f'entity_{uuid.uuid4().hex[0:12]}'
        
        item = {
            def_name: {
                'def_name': def_name,
                'class_name': None,
                'inherit': None,
                'entity': {
                    'layers': [],
                    f'entityDef {def_name}': {}
                }
            }
        }
        self.indexer.index(item)
        self.all_defs.add(def_name)
        self.list_model.insertRow(index.row(), item)

    def insert_entities_from_file(self, index:QModelIndex) -> None:
        file_path, _ = \
            QFileDialog.getOpenFileName(self, "Open file",
                "", "Map Entities Files (*.entities);;All Files (*)")
        if file_path != '':
            try:
                map = self.parser.parse_file(file_path)
                new_items = {}
                for entity in map.entities:
                    def_name = self.helper.get_def_name(entity)
                    self.all_defs.add(def_name)
                    if def_name in self.list_model.items:
                        self.indexer.remove([def_name])
                        self.list_model.remove_item(def_name)
                    new_items.update(self.data_item_from_entity(entity))
                self.indexer.index(new_items)
                self.list_model.insertRows(index.row(), len(new_items),
                                           new_items)
            except Exception as e:
                msg = f'Could insert entities file: {str(e)}'
                self.error_modal('Error inserting', msg)

    def remove_selected_entities(self) -> None:
        selected_indexes = \
            self.list_view.selectionModel().selectedIndexes()

        def_names = []
        for index in selected_indexes:
            def_name = index.data(role=self.list_model.DataKeyRole)
            def_names.append(def_name)
        
        for def_name in def_names:
            self.list_model.remove_item(def_name)
            self.all_defs.remove(def_name)
        
        self.indexer.remove(def_names)
    
    def export_selection(self) -> None:
        selected_indexes = \
            self.list_view.selectionModel().selectedIndexes()

        entities = []
        for index in selected_indexes:
            def_name = index.data(role=self.list_model.DataKeyRole)
            entities.append(self.list_model.items[def_name]['entity'])
        
        dialog = CustomSaveFileDialog(self, "Save File", "",
            "Map Entities Files (*.entities);;All Files (*)")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            file_path = dialog.selectedFiles()[0]
            compress = dialog.compress_checkbox.isChecked()
            if file_path:
                try:
                    map = EntitiesMap()
                    map.version = 7
                    map.hierarchy_version = 1
                    map.entities = entities
                    self.writer.write_to_file(map, file_path)
                    if compress:
                        self.oodle.compress_to_file(file_path,
                                                    file_path)
                    self.info_modal('File saved', 'The file was saved')
                except Exception as e:
                    msg = f'Could save entities file: {str(e)}'
                    self.error_modal('Error exporting', msg)

    # text editor actions -------------------------------------------
    def save_current_entity(self) -> None:
        try:
            current_index = \
                self.list_view.selectionModel().currentIndex()
            current_def_name = current_index.data(self.list_model.DataKeyRole)
            row = current_index.row()

            txt = self.text_edit.toPlainText()
            entity = self.entity_parser.parse(txt)
            new_def_name = self.helper.get_def_name(entity)
            item = self.data_item_from_entity(entity)
            
            # re-index the item
            self.indexer.remove([current_def_name])
            self.indexer.index(item)

            if current_def_name != new_def_name:
                if new_def_name in self.list_model.items:
                    self.list_model.remove_item(new_def_name)
                    self.all_defs.add(new_def_name)
                self.all_defs.remove(current_def_name)
                self.list_model.insertRow(row, item)
            else:
                self.list_model.items[new_def_name] = item[new_def_name]
        except Exception as e:
            msg = f'Failed to save entity: {str(e)}'
            self.error_modal('Error', msg)

    def clear_pos_coord_filters(self) -> None:
        self.pos_search_x_edit.clear()
        self.pos_search_y_edit.clear()
        self.pos_search_z_edit.clear()
    
    def highlight_text(self, keyword:str) -> None:
        format = QTextCharFormat()
        format.setBackground(QColor("yellow"))
        cursor = QTextCursor(self.text_edit.document())
        while not cursor.isNull() and not cursor.atEnd():
            cursor = self.text_edit.document().find(keyword, cursor)
            if not cursor.isNull():
                cursor.mergeCharFormat(format)

    def reset_highlight(self) -> None:
        char_format = QTextCharFormat()
        char_format.setBackground(QColor("transparent"))

        cursor = QTextCursor(self.text_edit.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.mergeCharFormat(char_format)
    
    def fix_item_arrays_in_editor(self) -> bool:
        txt = self.text_edit.toPlainText()
        data = None
        
        try:
            data = self.entity_parser.parse(txt)
        except Exception as e:
            msg = f'Error parsing editor text: {str(e)}'
            self.error_modal('Parsing error', msg)
            return False

        try:
            fixed_data = self.helper.fix_item_arrays_entity(data)
            fixed_text = self.writer.entities_to_str([fixed_data])
            self.text_edit.setText(fixed_text)
        except Exception as e:
            msg = f'Error fixing and writing the selected text: {str(e)}'
            self.error_modal('Error fixing array data', msg)
            return False
        return True

    # utility methods ----------------------------------------------
    def info_modal(self, title:str, msg:str) -> None:
        msgbox = QMessageBox()
        msgbox.setIcon(QMessageBox.Icon.Information)
        msgbox.setText(title)
        msgbox.setInformativeText(str(msg))
        msgbox.setWindowTitle("Info")
        msgbox.exec()

    def error_modal(self, title:str, msg:str) -> None:
        msgbox = QMessageBox()
        msgbox.setIcon(QMessageBox.Icon.Critical)
        msgbox.setText(title)
        msgbox.setInformativeText(str(msg))
        msgbox.setWindowTitle("Error")
        msgbox.exec()

    def create_dialog(self, title:str, msg:str) -> QDialog:
        dialog = QDialog()
        dialog.setWindowTitle(title)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.resize(300, 20)
        layout = QVBoxLayout()
        label = QLabel(msg)
        layout.addWidget(label)
        dialog.setLayout(layout)
        dialog.show()
        geometry = self.frameGeometry()
        dialog_geometry = dialog.frameGeometry()
        dialog_geometry.moveCenter(geometry.center())
        dialog.setGeometry(dialog_geometry)
        QApplication.processEvents()

        return dialog
    
    def is_float(self, txt:str) -> bool:
        try:
            float(txt)
            return True
        except ValueError: return False


class BookmarksWindow(QWidget):
    def __init__(self, options):
        super().__init__()
        self.options = options
        self._setup_window()
    
    def _setup_window(self):
        main_layout = QVBoxLayout() # main layout for entire window
        font = self.font()
        font_size = self.options.get('font.size', 10)
        font.setPointSize(font_size)
        self.setFont(font)
        self.setWindowIcon(QIcon('assets/icon.png'))

        main_layout.addWidget(self._setup_top_widget())
        main_layout.addWidget(self._setup_buttom_widget())

        self.setLayout(main_layout)
        self.setGeometry(900, 100, 400, 600)
        self.setWindowTitle('Bookmarks')
        self.show()
    
    def _setup_top_widget(self):
        self.edit_bookmark_button = QPushButton('Edit')
        self.edit_bookmark_button.clicked.connect(self.edit_bookmark)
        self.remove_bookmark_button = QPushButton('Remove')
        self.remove_bookmark_button.clicked.connect(self.remove_bookmark)

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.edit_bookmark_button)
        action_layout.addWidget(self.remove_bookmark_button)
        
        action_bar = QWidget()
        action_bar.setLayout(action_layout)

        return action_bar

    def _setup_buttom_widget(self):
        self.bookmark_list = QListWidget()
        self.bookmark_list.setDragEnabled(True)
        self.bookmark_list.setAcceptDrops(True)
        self.bookmark_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)

        return self.bookmark_list

    def edit_bookmark(self):
        item = self.bookmark_list.currentItem()
        if item:
            dialog = BookmarkNameDialog(item.text())
            if dialog.exec() == QDialog.DialogCode.Accepted:
                bm_name = dialog.line_edit.text()
                item.setText(bm_name)
    
    def remove_bookmark(self):
        item = self.bookmark_list.currentItem()
        if item:
            row = self.bookmark_list.row(item)
            self.bookmark_list.takeItem(row)


class CheckableComboBox(QComboBox):
    # Subclass Delegate to increase item height
    class Delegate(QStyledItemDelegate):
        def sizeHint(self, option, index):
            size = super().sizeHint(option, index)
            size.setHeight(20)
            return size

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make the combo editable to set a custom text, but readonly
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        # Make the lineedit the same color as QPushButton
        palette = QApplication.palette()
        palette.setBrush(QPalette.ColorRole.Base, palette.button())
        self.lineEdit().setPalette(palette)

        # Use custom delegate
        self.setItemDelegate(CheckableComboBox.Delegate())

        # Update the text when an item is toggled
        self.model().dataChanged.connect(self.updateText)

        # Hide and show popup when clicking the line edit
        self.lineEdit().installEventFilter(self)
        self.closeOnLineEditClick = False

        # Prevent popup from closing when clicking on an item
        self.view().viewport().installEventFilter(self)

    def resizeEvent(self, event):
        # Recompute text to elide as needed
        self.updateText()
        super().resizeEvent(event)

    def eventFilter(self, object, event):
        if object == self.lineEdit():
            if event.type() == QEvent.Type.MouseButtonRelease:
                if self.closeOnLineEditClick:
                    self.hidePopup()
                else:
                    self.showPopup()
                return True
            return False

        if object == self.view().viewport():
            if event.type() == QEvent.Type.MouseButtonRelease:
                index = self.view().indexAt(event.pos())
                item = self.model().item(index.row())

                if item.checkState() == Qt.CheckState.Checked:
                    item.setCheckState(Qt.CheckState.Unchecked)
                else:
                    item.setCheckState(Qt.CheckState.Checked)
                return True
        return False

    def showPopup(self):
        super().showPopup()
        # When the popup is displayed, a click on the lineedit should
        # close it
        self.closeOnLineEditClick = True

    def hidePopup(self):
        super().hidePopup()
        # Used to prevent immediate reopening when clicking on the
        # lineEdit
        self.startTimer(100)
        # Refresh the display text when closing
        self.updateText()

    def timerEvent(self, event):
        # After timeout, kill timer, and reenable click on line edit
        self.killTimer(event.timerId())
        self.closeOnLineEditClick = False

    def updateText(self):
        texts = []
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == \
                    Qt.CheckState.Checked:
                texts.append(self.model().item(i).text())
        txt = ", ".join(texts)

        self.setText(txt)

    def uncheckAll(self, checked=False):
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == \
                    Qt.CheckState.Checked:
                self.model().item(i).setCheckState(
                    Qt.CheckState.Unchecked)

    def setText(self, txt):
        # Compute elided text (with "...")
        metrics = QFontMetrics(self.lineEdit().font())
        elidedText = metrics.elidedText(
            txt, Qt.TextElideMode.ElideRight, self.lineEdit().width())
        self.lineEdit().setText(elidedText)

    def addItem(self, text, data=None):
        item = QStandardItem()
        item.setText(text)
        if data is None:
            item.setData(text)
        else:
            item.setData(data)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled |
                      Qt.ItemFlag.ItemIsUserCheckable)
        item.setData(Qt.CheckState.Unchecked,
                     Qt.ItemDataRole.CheckStateRole)
        self.model().appendRow(item)

    def addItems(self, texts, datalist=None):
        for i, text in enumerate(texts):
            try:
                data = datalist[i]
            except (TypeError, IndexError):
                data = None
            self.addItem(text, data)

    def currentData(self):
        # Return the list of selected items data
        res = []
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == \
                    Qt.CheckState.Checked:
                res.append(self.model().item(i).data())
        return res


class BookmarkNameDialog(QDialog):
    def __init__(self, bm_name=None):
        super().__init__()

        self.setWindowTitle("Bookmark name")
        self.setLayout(QVBoxLayout())

        self.label = QLabel("Enter the name for the bookmark:")
        self.line_edit = QLineEdit()
        if bm_name is not None:
            self.line_edit.setText(bm_name)

        self.layout().addWidget(self.label)
        self.layout().addWidget(self.line_edit)

        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")

        self.layout().addWidget(self.ok_button)
        self.layout().addWidget(self.cancel_button)

        self.ok_button.clicked.connect(self.accept_input)
        self.cancel_button.clicked.connect(self.reject)

    def accept_input(self):
        if self.line_edit.text().strip() == "":
            self.label.setText("Name cannot be empty!")
        else:
            self.accept()


class CustomSaveFileDialog(QFileDialog):
    """
    Adds a "Compress?" checkbox to the standard QFileDialog
    """
    def __init__(self, *args, **kwargs):
        super(CustomSaveFileDialog, self).__init__(*args, **kwargs)
        # the following option is needed to avoid self.layout() being
        # None on Windows (last tested with Qt5, not Qt6):
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.compress_checkbox = QCheckBox("Compress?", self)
        self.layout().addWidget(self.compress_checkbox,
                                self.layout().rowCount(), 0, 1, -1)


if __name__ == '__main__':
    freeze_support()  # for pyinstaller
    app = QApplication(sys.argv)
    file_path = None
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    window = MainWindow(file_path)
    
    sys.exit(app.exec())
