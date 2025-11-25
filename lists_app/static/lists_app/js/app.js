angular.module('groceryApp', [])
    .config(function ($httpProvider, $interpolateProvider) {
        $interpolateProvider.startSymbol('{[');
        $interpolateProvider.endSymbol(']}');
        // Enable Django CSRF token handling
        $httpProvider.defaults.xsrfCookieName = 'csrftoken';
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
    })
    .controller('MainCtrl', ['$scope', '$timeout', '$http', function ($scope, $timeout, $http) {
        const vm = this;
        vm.lists = [];
        vm.currentList = null;
        vm.items = [];
        vm.socket = null;
        vm.connected = false;
        vm.newItem = { name: '', section: null};
        vm.pending = {};
        vm.sections = [];
        vm.grouped = {};
        vm.sectionOrder = [];
        vm.noneSectionName = '_none';

        // ===== Load all lists from backend =====
        vm.loadLists = function () {
            $http.get('/api/lists/').then(res => {
                vm.lists = res.data;
            });
        };

        // ===== Create new list =====
        vm.createList = function () {
            const name = prompt('Name for new list:');
            if (!name) return;
            $http.post('/api/lists/', { name }).then(res => {
                vm.lists.push(res.data);
                vm.openList(res.data);
            });
        };

        // ===== Open an existing list =====
        vm.openList = function (list) {
            vm.currentList = list;
            vm.connect(list.id);
        };

        // ===== Leave current list =====
        vm.leaveList = function () {
            if (vm.socket) vm.socket.close();
            vm.currentList = null;
            vm.items = [];
        };

        // ===== WebSocket setup =====
        vm.connect = function (listId) {
            const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
            const wsUrl = `${protocol}://127.0.0.1:8000/ws/list/${listId}/`;
            vm.socket = new WebSocket(wsUrl);

            vm.socket.onopen = () => $scope.$apply(() => vm.connected = true);
            vm.socket.onclose = () => $scope.$apply(() => vm.connected = false);
            vm.socket.onerror = err => console.error('WS error', err);
            vm.socket.onmessage = evt => $scope.$apply(() => handleMessage(JSON.parse(evt.data)));
        };

        function send(msg) {
            if (vm.socket && vm.socket.readyState === WebSocket.OPEN)
                vm.socket.send(JSON.stringify(msg));
        }

        function handleMessage(msg) {
            // Normal websocket actions handled by server:
            if (msg.action === 'initial') {
                vm.items = msg.items.slice();
                // Initialize snapshots
                vm._lastSnapshot = {};
                vm.items.forEach(item => {
                    vm._lastSnapshot[item.id] = angular.copy(item);
                });
            }
            if (msg.action === 'added') {
                vm.items.push(msg.item);
                vm._lastSnapshot[msg.item.id] = angular.copy(msg.item);
            }
            if (msg.action === 'updated') {
                const i = vm.items.findIndex(it => it.id === msg.item.id);
                if (i > -1) {
                    vm.items[i] = msg.item;
                } else {
                    vm.items.push(msg.item);
                }
                vm._lastSnapshot[msg.item.id] = angular.copy(msg.item);
            }
            if (msg.action === 'deleted') {
                vm.items = vm.items.filter(it => it.id !== msg.item_id);
                delete vm._lastSnapshot[msg.item_id];
            }

            // regroup will run through the $watch on vm.items
        }

        // ===== Inline editing logic =====
        vm.queueUpdate = function (it) {
            if (!it.id) return;
            if (vm.pending[it.id]) $timeout.cancel(vm.pending[it.id]);
            vm.pending[it.id] = $timeout(() => vm.commitUpdate(it), 800);
        };

        vm.commitUpdate = function (it) {
            if (!it.id) return;

            const old = vm._lastSnapshot[it.id];
            const oldSectionName = old && old.section ? old.section.name : vm.noneSectionName;
            const newSectionName = it.section ? it.section.name : vm.noneSectionName;

            // Detect section change
            if (oldSectionName !== newSectionName) {
                // Assign new proper order for the new section
                const list = vm.grouped[newSectionName] || [];
                let nextOrder = 1;
                if (list.length > 0) {
                    // Exclude the current item from the max calculation if it's already in the list
                    const otherItems = list.filter(item => item.id !== it.id);
                    if (otherItems.length > 0) {
                        nextOrder = Math.max(...otherItems.map(i => i.order || 0)) + 1;
                    }
                }

                it.order = nextOrder;

                // Update the snapshot
                vm._lastSnapshot[it.id] = angular.copy(it);
            }

            sendUpdateItem(it);
        };

        function sendUpdateItem(it) {
            // include order and section so backend can persist
            // section may be an object (ng-model bound), keep same shape as other messages
            const payload = {
                id: it.id,
                name: it.name,
                section: it.section || null
            };
            if (typeof it.order !== 'undefined') payload.order = it.order;
            send({ action: 'update', item: payload });
        }

        vm.toggle = function (it) {
            send({ action: 'toggle', item: { id: it.id, checked: it.checked } });
        };

        vm.remove = function (it) {
            send({ action: 'delete', item: { id: it.id } });
        };

        // ===== Add new item =====
        vm.handleKey = function (event) {
            if (event.which === 13) {
                event.preventDefault();
                vm.addNewItem();
            }
        };

        vm.handleBlur = function () {
            if (vm.newItem.name.trim() !== '')
                vm.addNewItem();
        };

        vm.addNewItem = function () {
            if (!vm.newItem.name.trim()) return;

            // Determine section key (name) as used by grouping
            const secName = vm.newItem.section ? vm.newItem.section.name : vm.noneSectionName;
            const list = vm.grouped[secName] || [];

            // Compute next order - use the highest existing order + 1
            // If no items exist, start with 1
            let nextOrder = 1;
            if (list.length > 0) {
                // Find the maximum order in the current section
                const orders = list.map(it => it.order || 0);
                nextOrder = Math.max(...orders) + 1;
            }

            const toSend = angular.copy(vm.newItem);
            toSend.order = nextOrder;

            // Send the new item with the calculated order
            send({ action: 'add', item: toSend });

            // Reset newItem
            vm.newItem = { name: '', section: null };
        };

        // ===== Sections management =====
        vm.loadSections = function () {
            $http.get('/api/sections/').then(res => {
                // ensure array and sorted by 'order' asc
                vm.sections = res.data.slice().sort((a, b) => (a.order || 0) - (b.order || 0));
                rebuildSectionOrder();
            });
        };

        function rebuildSectionOrder() {
            // sectionOrder is an array of section names in the order defined by vm.sections
            vm.sectionOrder = vm.sections.map(s => s.name);

            // Always include the uncategorized group at the end if not present
            if (vm.sectionOrder.indexOf(vm.noneSectionName) === -1) {
                vm.sectionOrder.push(vm.noneSectionName);
            }
        }

        function regroup() {
            vm.grouped = {};

            // initialize groups for all known sections to keep empty groups available
            vm.sections.forEach(s => {
                vm.grouped[s.name] = [];
            });
            vm.grouped[vm.noneSectionName] = vm.grouped[vm.noneSectionName] || [];

            // distribute items into groups
            vm.items.forEach(item => {
                const key = item.section ? item.section.name : vm.noneSectionName;
                if (!vm.grouped[key]) vm.grouped[key] = [];
                vm.grouped[key].push(item);

                // Ensure snapshot exists
                if (!vm._lastSnapshot[item.id]) {
                    vm._lastSnapshot[item.id] = angular.copy(item);
                }
            });

            // sort items inside each group by item.order (asc). default to 0 if missing.
            Object.keys(vm.grouped).forEach(k => {
                vm.grouped[k].sort((a, b) => (a.order || 0) - (b.order || 0));
            });

            // rebuild sectionOrder from current vm.sections (sorted by their order)
            rebuildSectionOrder();
        }

        // Call regroup() whenever vm.items changes
        $scope.$watch(
            () => vm.items,
            () => regroup(),
            true
        );

        // ===== Reordering items within a section =====
        vm.moveItem = function (item, direction) {
            if (!item) return;
            const secName = item.section ? item.section.name : vm.noneSectionName;
            const list = vm.grouped[secName];
            if (!list) return;

            const idx = list.findIndex(it => it.id === item.id);
            if (idx === -1) return;

            const newIdx = idx + direction;
            if (newIdx < 0 || newIdx >= list.length) return;

            const other = list[newIdx];

            // swap order values (if one is undefined, assign sensible defaults)
            if (typeof item.order === 'undefined') item.order = idx + 1;
            if (typeof other.order === 'undefined') other.order = newIdx + 1;

            const tmp = item.order;
            item.order = other.order;
            other.order = tmp;

            // send updates immediately so backend persists the new ordering
            sendUpdateItem(item);
            sendUpdateItem(other);

            // update local grouping (sorted by order)
            list.sort((a, b) => (a.order || 0) - (b.order || 0));
        };

        // ===== Reordering whole sections =====
        vm.moveSection = function (sectionName, direction) {
            // if trying to move uncategorized, do nothing
            if (sectionName === vm.noneSectionName) return;

            const idx = vm.sections.findIndex(s => s.name === sectionName);
            if (idx === -1) return;

            const newIdx = idx + direction;
            if (newIdx < 0 || newIdx >= vm.sections.length) return;

            // swap order numbers
            const sec = vm.sections[idx];
            const other = vm.sections[newIdx];

            const secOrder = sec.order || 0;
            const otherOrder = other.order || 0;

            // swap numerical order values
            const tmpOrder = secOrder;
            sec.order = otherOrder;
            other.order = tmpOrder;

            // persist both sections' order to backend via PATCH
            $http.patch(`/api/sections/${sec.id}/`, { order: sec.order }).then(() => {
                // success - nothing extra required
            }).catch(err => {
                console.error('Failed to update section order for', sec, err);
            });

            $http.patch(`/api/sections/${other.id}/`, { order: other.order }).then(() => {
                // success
            }).catch(err => {
                console.error('Failed to update section order for', other, err);
            });

            // reorder vm.sections array and rebuild order array used by the UI
            vm.sections.sort((a, b) => (a.order || 0) - (b.order || 0));
            rebuildSectionOrder();
        };

        // ===== Convenience: find section object by name or id =====
        vm.getSectionByName = function (name) {
            return vm.sections.find(s => s.name === name) || null;
        };

        vm.getSectionById = function (id) {
            return vm.sections.find(s => s.id === id) || null;
        };

        // ===== Theme toggle (same as before) =====
        const toggle = document.getElementById('theme-toggle');
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-mode');
            toggle.checked = true;
        }
        toggle.addEventListener('change', function () {
            if (this.checked) {
                document.body.classList.add('dark-mode');
                localStorage.setItem('theme', 'dark');
            } else {
                document.body.classList.remove('dark-mode');
                localStorage.setItem('theme', 'light');
            }
        });

        // ===== Initial load =====
        vm.loadLists();
        vm.loadSections();

    }]);
