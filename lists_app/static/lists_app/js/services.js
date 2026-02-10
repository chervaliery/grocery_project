/**
 * API and WebSocket services
 */
(function () {
  'use strict';
  function defaultListName() {
    var d = new Date();
    var day = ('0' + d.getDate()).slice(-2);
    var month = ('0' + (d.getMonth() + 1)).slice(-2);
    var year = d.getFullYear();
    return 'Liste du ' + day + '/' + month + '/' + year;
  }

  angular.module('listsApp')
    .factory('ListsApi', function ($http) {
      var base = '/api';
      return {
        defaultListName: defaultListName,
        getLists: function () {
          return $http.get(base + '/lists/').then(function (r) { return r.data; });
        },
        createList: function (name) {
          return $http.post(base + '/lists/', { name: name || defaultListName() }).then(function (r) { return r.data; });
        },
        getList: function (listId) {
          return $http.get(base + '/lists/' + listId + '/').then(function (r) { return r.data; });
        },
        patchList: function (listId, data) {
          return $http.patch(base + '/lists/' + listId + '/', data).then(function (r) { return r.data; });
        },
        deleteList: function (listId) {
          return $http.delete(base + '/lists/' + listId + '/');
        },
        parseImport: function (listId, text) {
          return $http.post(base + '/lists/' + listId + '/parse-import/', { text: text }).then(function (r) { return r.data; });
        },
        deduplicateList: function (listId) {
          return $http.post(base + '/lists/' + listId + '/deduplicate/').then(function (r) { return r.data; });
        }
      };
    })
    .factory('ListWebSocket', function ($rootScope) {
      var ws = null;
      var listId = null;
      var reconnectTimer = null;
      var currentOnMessage = null;
      var api = {
        connect: function (lid, onMessage) {
          if (ws && listId === lid) return;
          listId = lid;
          currentOnMessage = onMessage;
          if (ws) try { ws.close(); } catch (e) {}
          var proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
          var url = proto + '//' + window.location.host + '/ws/list/' + lid + '/';
          ws = new WebSocket(url);
          ws.onmessage = function (event) {
            try {
              var data = JSON.parse(event.data);
              $rootScope.$apply(function () { if (currentOnMessage) currentOnMessage(data); });
            } catch (e) {}
          };
          ws.onclose = function () {
            if (reconnectTimer) clearTimeout(reconnectTimer);
            reconnectTimer = setTimeout(function () {
              if (listId && currentOnMessage) api.connect(listId, currentOnMessage);
            }, 3000);
          };
        },
        send: function (payload) {
          if (ws && ws.readyState === WebSocket.OPEN)
            ws.send(JSON.stringify(payload));
        },
        disconnect: function () {
          if (reconnectTimer) clearTimeout(reconnectTimer);
          reconnectTimer = null;
          listId = null;
          currentOnMessage = null;
          if (ws) try { ws.close(); ws = null; } catch (e) {}
        }
      };
      return api;
    });
})();
