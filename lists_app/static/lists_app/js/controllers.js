/**
 * Controllers: list selection and list detail
 */
(function () {
  'use strict';
  angular.module('listsApp')
    .controller('ListSelectionCtrl', function ($location, ListsApi) {
      var vm = this;
      vm.lists = [];
      vm.loading = true;
      vm.error = null;
      function load() {
        vm.loading = true;
        vm.error = null;
        ListsApi.getLists().then(function (data) {
          vm.lists = data.lists || [];
          vm.loading = false;
        }).catch(function () {
          vm.error = 'Impossible de charger les listes.';
          vm.loading = false;
        });
      }
      vm.newListName = ListsApi.defaultListName();
      vm.createList = function () {
        var name = (vm.newListName || '').trim() || undefined;
        ListsApi.createList(name).then(function (list) {
          vm.newListName = '';
          $location.path('/list/' + list.id);
        }).catch(function () { vm.error = 'Erreur à la création.'; });
      };
      vm.showArchived = false;
      vm.openList = function (id) {
        $location.path('/list/' + id);
      };
      vm.archiveList = function (id) {
        ListsApi.patchList(id, { archived: true }).then(load);
      };
      vm.restoreList = function (id) {
        ListsApi.patchList(id, { archived: false }).then(load);
      };
      vm.deleteList = function (id) {
        if (!confirm('Supprimer cette liste ?')) return;
        ListsApi.deleteList(id).then(load);
      };
      load();
    })
    .controller('ListDetailCtrl', function ($routeParams, $location, ListsApi, ListWebSocket) {
      var vm = this;
      vm.listId = $routeParams.listId;
      vm.list = null;
      vm.sections = [];
      vm.hideChecked = true;
      vm.newItemName = '';
      vm.loading = true;
      vm.error = null;
      function applyList(data) {
        vm.list = data;
        vm.sections = data.sections || [];
      }
      function load() {
        vm.loading = true;
        ListsApi.getList(vm.listId).then(function (data) {
          applyList(data);
          vm.loading = false;
        }).catch(function () {
          vm.error = 'Liste introuvable.';
          vm.loading = false;
        });
      }
      ListWebSocket.connect(vm.listId, function (msg) {
        if (msg.action === 'list_updated' && msg.list) applyList(msg.list);
        if (msg.action === 'item_added' && msg.item) {
          var found = false;
          vm.sections.forEach(function (s) {
            if (s.section_id === msg.item.section_id) {
              s.items = s.items || [];
              s.items.push(msg.item);
              found = true;
            }
          });
          if (!found) load();
        }
        if (msg.action === 'item_updated' && msg.item) {
          vm.sections.forEach(function (s) {
            (s.items || []).forEach(function (it, i) {
              if (it.id === msg.item.id) s.items[i] = msg.item;
            });
          });
        }
        if (msg.action === 'item_deleted' && msg.item_id) {
          vm.sections.forEach(function (s) {
            s.items = (s.items || []).filter(function (it) { return it.id !== msg.item_id; });
          });
        }
      });
      vm.newItemQuantity = '';
      vm.newItemNotes = '';
      vm.importText = '';
      vm.importMessage = '';
      vm.importLoading = false;
      vm.deduplicateMessage = '';
      vm.editingListName = false;
      vm.listNameEdit = '';
      vm.startEditListName = function () {
        vm.listNameEdit = vm.list.name || '';
        vm.editingListName = true;
      };
      vm.cancelEditListName = function () {
        vm.editingListName = false;
      };
      vm.saveListName = function () {
        var name = (vm.listNameEdit || '').trim();
        if (!name) return;
        ListsApi.patchList(vm.listId, { name: name }).then(function (data) {
          vm.list.name = data.name;
          vm.editingListName = false;
        });
      };
      vm.listNameKeydown = function (e) {
        if (e.which === 13) vm.saveListName();
        if (e.which === 27) vm.cancelEditListName();
      };
      function normalizeItemName(s) {
        if (s == null) return '';
        s = String(s).trim().replace(/\s+/g, ' ');
        if (!s) return '';
        return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
      }
      vm.addItem = function () {
        var name = normalizeItemName(vm.newItemName);
        if (!name) return;
        ListWebSocket.send({
          action: 'add_item',
          name: name,
          quantity: (vm.newItemQuantity || '').trim(),
          notes: (vm.newItemNotes || '').trim()
        });
        vm.newItemName = '';
        vm.newItemQuantity = '';
        vm.newItemNotes = '';
      };
      vm.toggleChecked = function (item) {
        ListWebSocket.send({ action: 'check_item', item_id: item.id, checked: !item.checked });
      };
      vm.deleteItem = function (item) {
        ListWebSocket.send({ action: 'delete_item', item_id: item.id });
      };
      vm.editingItemId = null;
      vm.editItemName = '';
      vm.editItemQuantity = '';
      vm.editItemNotes = '';
      vm.startEditItem = function (item) {
        vm.editingItemId = item.id;
        vm.editItemName = item.name || '';
        vm.editItemQuantity = item.quantity || '';
        vm.editItemNotes = item.notes || '';
      };
      vm.cancelEditItem = function () {
        vm.editingItemId = null;
      };
      vm.saveEditItem = function (item) {
        var name = normalizeItemName(vm.editItemName);
        if (!name) return;
        ListWebSocket.send({
          action: 'update_item',
          item_id: item.id,
          name: name,
          quantity: (vm.editItemQuantity || '').trim(),
          notes: (vm.editItemNotes || '').trim()
        });
        vm.editingItemId = null;
      };
      vm.reorderItems = function (section, itemIds) {
        if (!itemIds || !itemIds.length) return;
        ListWebSocket.send({
          action: 'reorder_items',
          item_orders: [{ section_id: section.section_id, item_ids: itemIds }]
        });
      };
      vm.getVisibleItems = function (section) {
        if (!section || !section.items) return [];
        if (!vm.hideChecked) return section.items;
        return section.items.filter(function (it) { return !it.checked; });
      };
      vm.getCheckedCount = function (section) {
        if (!section || !section.items) return 0;
        return section.items.filter(function (it) { return it.checked; }).length;
      };
      vm.allSectionsEmpty = function () {
        if (!vm.hideChecked || !vm.sections.length) return false;
        return vm.sections.every(function (section) {
          return vm.getVisibleItems(section).length === 0;
        });
      };
      vm.getSectionSlugs = function () {
        return (vm.sections || []).map(function (s) { return s.section_slug; });
      };
      vm.parseImportLines = function () {
        var text = (vm.importText || '').trim();
        if (!text) return [];
        var slugs = vm.getSectionSlugs();
        var lines = text.split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
        var out = [];
        for (var i = 0; i < lines.length; i++) {
          var line = lines[i];
          var name = line;
          var quantity = '';
          var section_slug = null;
          var sep = line.indexOf(':');
          if (sep === -1) sep = line.indexOf('|');
          if (sep > 0) {
            var prefix = line.slice(0, sep).trim().toLowerCase();
            if (slugs.indexOf(prefix) !== -1) {
              section_slug = prefix;
              name = line.slice(sep + 1).trim();
            }
          }
          var spaceColonSpace = (name || '').indexOf(' : ');
          if (spaceColonSpace !== -1) {
            quantity = (name.slice(spaceColonSpace + 3) || '').trim();
            name = (name.slice(0, spaceColonSpace) || '').trim();
          } else {
            var qtyMatch = (name || '').match(/^(\d+)\s+(.+)$/);
            if (qtyMatch) {
              quantity = qtyMatch[1];
              name = qtyMatch[2].trim();
            }
          }
          if (!name) continue;
          out.push({ name: name, quantity: quantity, notes: '', section_slug: section_slug });
        }
        return out;
      };
      function applyImportedItems(items, message) {
        items.forEach(function (it) {
          var payload = { action: 'add_item', name: it.name, quantity: it.quantity || '', notes: it.notes || '' };
          if (it.section_slug) payload.section_slug = it.section_slug;
          ListWebSocket.send(payload);
        });
        vm.importText = '';
        vm.importMessage = message;
        var modalEl = document.getElementById('importModal');
        if (modalEl && window.bootstrap && window.bootstrap.Modal) {
          var modal = window.bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
        }
        setTimeout(function () { vm.importMessage = ''; }, 3000);
      }
      vm.doImport = function () {
        vm.importMessage = '';
        var text = (vm.importText || '').trim();
        if (!text) {
          vm.importMessage = 'Aucun texte à importer.';
          return;
        }
        vm.importLoading = true;
        vm.importMessage = 'Analyse en cours…';
        ListsApi.parseImport(vm.listId, text).then(function (data) {
          var items = data.items || [];
          if (items.length === 0) {
            vm.importMessage = 'Aucun article reconnu.';
            return;
          }
          applyImportedItems(items, items.length + ' article(s) importé(s).');
        }).catch(function () {
          var items = vm.parseImportLines();
          if (items.length === 0) {
            vm.importMessage = 'Aucun article à importer.';
            return;
          }
          applyImportedItems(items, items.length + ' article(s) importé(s) (analyse locale).');
        }).finally(function () {
          vm.importLoading = false;
        });
      };
      vm.deduplicate = function () {
        ListsApi.deduplicateList(vm.listId).then(function (data) {
          applyList(data);
          vm.deduplicateMessage = 'Liste dédupliquée.';
          setTimeout(function () { vm.deduplicateMessage = ''; }, 3000);
        }).catch(function () {
          vm.error = 'Erreur lors de la déduplication.';
        });
      };
      vm.back = function () {
        ListWebSocket.disconnect();
        $location.path('/');
      };
      load();
    });
})();
