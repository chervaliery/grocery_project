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
        vm.newItem = { name: '', section: null };
        vm.pending = {};
        vm.sections = [];
        vm.grouped = {};
        vm.sectionOrder = [];
        vm._lastSnapshot = {};
        vm.noneSectionName = '_none';

        // Drag and drop state
        vm.draggedItem = null;
        vm.draggedSection = null;
        vm.dragOverItem = null;
        vm.dragOverSection = null;

        // ===== Drag and Drop Handlers =====
        vm.initDragAndDrop = function () {
            document.addEventListener('dragstart', function (e) {
                console.log('Drag start on:', e.target);

                if (e.target.classList.contains('drag-handle')) {
                    const handle = e.target;

                    if (handle.classList.contains('item-drag-handle')) {
                        const itemId = handle.getAttribute('data-item-id');
                        console.log('Found item drag handle for ID:', itemId);
                        vm.draggedItem = vm.items.find(it => it.id == itemId);
                        if (vm.draggedItem) {
                            e.dataTransfer.setData('text/plain', 'item:' + itemId);
                            e.dataTransfer.effectAllowed = 'move';
                            console.log('Drag start - item:', vm.draggedItem.name);
                        } else {
                            console.error('Could not find item with ID:', itemId);
                        }
                    } else if (handle.classList.contains('section-drag-handle')) {
                        const sectionName = handle.getAttribute('data-section-name');
                        vm.draggedSection = sectionName;
                        e.dataTransfer.setData('text/plain', 'section:' + sectionName);
                        e.dataTransfer.effectAllowed = 'move';
                        console.log('Drag start - section:', vm.draggedSection);
                    }

                    // Add visual feedback
                    handle.style.opacity = '0.4';
                }
            });

            document.addEventListener('dragend', function (e) {
                console.log('Drag end');
                if (e.target.classList.contains('drag-handle')) {
                    e.target.style.opacity = '1';
                    vm.draggedItem = null;
                    vm.draggedSection = null;
                    vm.dragOverItem = null;
                    vm.dragOverSection = null;

                    // Remove all drag-over classes
                    document.querySelectorAll('.drag-over, .section-drag-over').forEach(el => {
                        el.classList.remove('drag-over', 'section-drag-over');
                    });
                }
            });

            document.addEventListener('dragover', function (e) {
                e.preventDefault(); // Necessary to allow drop

                if (vm.draggedItem || vm.draggedSection) {
                    e.dataTransfer.dropEffect = 'move';

                    // Remove previous drag-over classes
                    document.querySelectorAll('.drag-over, .section-drag-over').forEach(el => {
                        el.classList.remove('drag-over', 'section-drag-over');
                    });

                    // Find the closest item or section container
                    let targetElement = e.target;

                    while (targetElement && targetElement !== document) {
                        // Check if it's an item element
                        if (targetElement.classList && targetElement.classList.contains('item') && targetElement.hasAttribute('data-item-id')) {
                            const itemId = targetElement.getAttribute('data-item-id');
                            const item = vm.items.find(it => it.id == itemId);
                            if (item && vm.draggedItem && item.id !== vm.draggedItem.id) {
                                vm.dragOverItem = item;
                                targetElement.classList.add('drag-over');
                                console.log('Drag over item:', item.name);
                                break;
                            }
                        }
                        // Check if it's a section container
                        else if (targetElement.classList && targetElement.classList.contains('section-container')) {
                            const sectionName = targetElement.getAttribute('data-section-name');
                            if (vm.draggedSection && sectionName !== vm.draggedSection && sectionName !== vm.noneSectionName) {
                                vm.dragOverSection = sectionName;
                                targetElement.classList.add('section-drag-over');
                                console.log('Drag over section:', sectionName);
                                break;
                            } else if (vm.draggedItem) {
                                // Item being dragged over a section container
                                targetElement.classList.add('drag-over');
                                console.log('Drag over section container for item');
                                break;
                            }
                        }
                        targetElement = targetElement.parentElement;
                    }
                }
            });

            document.addEventListener('drop', function (e) {
                e.preventDefault();
                console.log('Drop event - draggedItem:', vm.draggedItem, 'dragOverItem:', vm.dragOverItem, 'draggedSection:', vm.draggedSection, 'dragOverSection:', vm.dragOverSection);

                if (vm.draggedItem && vm.dragOverItem) {
                    // Item dropped on another item - reorder items
                    console.log('Dropping item on item:', vm.draggedItem.name, '->', vm.dragOverItem.name);
                    vm.handleItemDrop(vm.draggedItem, vm.dragOverItem);
                } else if (vm.draggedSection && vm.dragOverSection) {
                    // Section dropped on another section - reorder sections
                    console.log('Dropping section on section:', vm.draggedSection, '->', vm.dragOverSection);
                    vm.handleSectionDrop(vm.draggedSection, vm.dragOverSection);
                } else if (vm.draggedItem) {
                    // Item dropped in empty space or section area
                    console.log('Item dropped in empty space, looking for section...');
                    let targetElement = e.target;
                    let targetSection = null;

                    // Traverse up to find section container
                    while (targetElement && targetElement !== document) {
                        if (targetElement.classList && targetElement.classList.contains('section-container')) {
                            const sectionName = targetElement.getAttribute('data-section-name');
                            targetSection = vm.getSectionByName(sectionName);
                            console.log('Found target section:', targetSection ? targetSection.name : 'none');
                            break;
                        }
                        targetElement = targetElement.parentElement;
                    }

                    if (targetSection) {
                        const currentSectionName = vm.draggedItem.section ? vm.draggedItem.section.name : vm.noneSectionName;
                        const targetSectionName = targetSection ? targetSection.name : vm.noneSectionName;

                        console.log('Current section:', currentSectionName, 'Target section:', targetSectionName);

                        if (currentSectionName !== targetSectionName) {
                            console.log('Moving item to different section');
                            vm.moveItemToSection(vm.draggedItem, targetSection);
                        } else {
                            console.log('Item already in target section');
                        }
                    } else {
                        console.log('No target section found');
                    }
                } else {
                    console.log('No valid drop target found');
                }

                // Clean up
                vm.draggedItem = null;
                vm.draggedSection = null;
                vm.dragOverItem = null;
                vm.dragOverSection = null;

                document.querySelectorAll('.drag-over, .section-drag-over').forEach(el => {
                    el.classList.remove('drag-over', 'section-drag-over');
                });
            });
        };

        vm.handleItemDrop = function (draggedItem, targetItem) {
            if (!draggedItem || !targetItem || draggedItem.id === targetItem.id) return;

            console.log('Handling item drop:', draggedItem.name, '->', targetItem.name);

            const draggedSectionName = draggedItem.section ? draggedItem.section.name : vm.noneSectionName;
            const targetSectionName = targetItem.section ? targetItem.section.name : vm.noneSectionName;

            // If items are in different sections, move dragged item to target section first
            if (draggedSectionName !== targetSectionName) {
                console.log('Moving item to different section before reordering');
                vm.moveItemToSection(draggedItem, targetItem.section);
                // Wait for section change to complete before reordering
                $timeout(() => {
                    vm.reorderItemInSection(draggedItem, targetItem);
                }, 100);
            } else {
                // Items are in same section - just reorder
                console.log('Reordering items within same section');
                vm.reorderItemInSection(draggedItem, targetItem);
            }
        };

        vm.reorderItemInSection = function (draggedItem, targetItem) {
            const sectionName = draggedItem.section ? draggedItem.section.name : vm.noneSectionName;
            const list = vm.grouped[sectionName] || [];

            console.log('Reordering in section:', sectionName, 'list length:', list.length);

            if (list.length < 2) return;

            const draggedIndex = list.findIndex(it => it.id === draggedItem.id);
            const targetIndex = list.findIndex(it => it.id === targetItem.id);

            console.log('Dragged index:', draggedIndex, 'Target index:', targetIndex);

            if (draggedIndex === -1 || targetIndex === -1) return;

            // Remove dragged item from array
            const [movedItem] = list.splice(draggedIndex, 1);
            // Insert at target position
            list.splice(targetIndex, 0, movedItem);

            console.log('New order:', list.map(it => it.name));

            // Reassign orders based on new positions
            list.forEach((item, index) => {
                item.order = index + 1;
                console.log('Updating order for', item.name, 'to', item.order);
                sendUpdateItem(item);
            });

            // Force UI update
            $scope.$apply();
        };

        vm.handleSectionDrop = function (draggedSectionName, targetSectionName) {
            if (!draggedSectionName || !targetSectionName || draggedSectionName === targetSectionName) return;

            console.log('Handling section drop:', draggedSectionName, '->', targetSectionName);

            const draggedIndex = vm.sections.findIndex(s => s.name === draggedSectionName);
            const targetIndex = vm.sections.findIndex(s => s.name === targetSectionName);

            if (draggedIndex === -1 || targetIndex === -1) return;

            // Swap section orders
            const draggedSection = vm.sections[draggedIndex];
            const targetSection = vm.sections[targetIndex];

            const tempOrder = draggedSection.order;
            draggedSection.order = targetSection.order;
            targetSection.order = tempOrder;

            console.log('Swapping section orders:', draggedSection.name, draggedSection.order, '<=>', targetSection.name, targetSection.order);

            // Send section reorder through WebSocket instead of HTTP
            const sectionOrders = {};
            sectionOrders[draggedSection.id] = draggedSection.order;
            sectionOrders[targetSection.id] = targetSection.order;

            send({
                action: 'reorder_sections',
                item: { section_orders: sectionOrders }
            });

            // Update local ordering
            vm.sections.sort((a, b) => (a.order || 0) - (b.order || 0));
            rebuildSectionOrder();

            // Force UI update
            $scope.$apply();
        };

        vm.moveItemToSection = function (item, newSection) {
            if (!item) return;

            const oldSectionName = item.section ? item.section.name : vm.noneSectionName;
            const newSectionName = newSection ? newSection.name : vm.noneSectionName;

            if (oldSectionName === newSectionName) return;

            console.log('Moving item', item.name, 'from', oldSectionName, 'to', newSectionName);

            // Update item's section
            item.section = newSection;

            // Calculate new order in target section
            const targetList = vm.grouped[newSectionName] || [];
            let newOrder = 1;
            if (targetList.length > 0) {
                newOrder = Math.max(...targetList.map(it => it.order || 0)) + 1;
            }
            item.order = newOrder;

            console.log('New order for item:', newOrder);

            // Send update to backend
            sendUpdateItem(item);

            // Force UI update
            $scope.$apply();
        };

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
            if (msg.action === 'sections_reordered') {
                // Update sections with new order from WebSocket
                console.log('Received sections reordered:', msg.sections);
                msg.sections.forEach(updatedSection => {
                    const existingSection = vm.sections.find(s => s.id === updatedSection.id);
                    if (existingSection) {
                        existingSection.order = updatedSection.order;
                    }
                });
                // Re-sort sections and rebuild order
                vm.sections.sort((a, b) => (a.order || 0) - (b.order || 0));
                rebuildSectionOrder();
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

            // compute next order (backend expects order inside the section)
            let nextOrder = 1; // assuming backend orders start at 1 as in example
            if (list.length > 0) {
                const max = Math.max.apply(null, list.map(it => (typeof it.order !== 'undefined' ? it.order : 0)));
                nextOrder = max + 1;
            }

            const toSend = angular.copy(vm.newItem);
            toSend.order = nextOrder;

            // keep section as object or null (same shape server expects in your protocol)
            send({ action: 'add', item: toSend });

            // reset newItem (section stays null)
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

        // ===== Convenience: find section object by name or id =====
        vm.getSectionByName = function (name) {
            return vm.sections.find(s => s.name === name) || null;
        };

        vm.getSectionById = function (id) {
            return vm.sections.find(s => s.id === id) || null;
        };

        // ===== Theme toggle =====
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

        // Initialize drag and drop after a brief delay to ensure DOM is ready
        $timeout(() => {
            vm.initDragAndDrop();
        }, 100);

    }]);