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
            if (msg.action === 'initial') vm.items = msg.items.slice();
            if (msg.action === 'added') vm.items.push(msg.item);
            if (msg.action === 'updated') {
                const i = vm.items.findIndex(it => it.id === msg.item.id);
                if (i > -1) vm.items[i] = msg.item;
                else vm.items.push(msg.item);
            }
            if (msg.action === 'deleted') vm.items = vm.items.filter(it => it.id !== msg.item_id);
        }

        // ===== Inline editing logic =====
        vm.queueUpdate = function (it) {
            if (!it.id) return;
            if (vm.pending[it.id]) $timeout.cancel(vm.pending[it.id]);
            vm.pending[it.id] = $timeout(() => vm.commitUpdate(it), 800);
        };

        vm.commitUpdate = function (it) {
            if (!it.id) return;
            send({ action: 'update', item: { id: it.id, name: it.name, section: it.section } });
        };

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
            send({ action: 'add', item: angular.copy(vm.newItem) });
            vm.newItem = { name: '', section: {} };
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
        vm.sections = [];

        // Load sections initially
        vm.loadSections = function () {
            $http.get('/api/sections/').then(res => {
                vm.sections = res.data;
            });
        };

        function regroup() {
            vm.grouped = {};

            vm.items.forEach(item => {
                const key = item.section ? item.section.name : "_none";
                if (!vm.grouped[key]) vm.grouped[key] = [];
                vm.grouped[key].push(item);
            });
        }

        // Call regroup() whenever vm.items changes
        $scope.$watch(
            () => vm.items,
            () => regroup(),
            true
        );
        // Load initial list overview
        vm.loadLists();
        vm.loadSections();

    }]);
