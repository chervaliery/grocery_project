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
      var onStateChange = null;
      var connectionState = 'disconnected';
      var reconnectAttempts = 0;
      var maxAutoReconnectAttempts = 5;

      function setState(state) {
        if (connectionState === state) return;
        connectionState = state;
        if (onStateChange) {
          $rootScope.$evalAsync(function () { onStateChange(state); });
        }
      }

      function tryReconnect() {
        if (reconnectTimer) clearTimeout(reconnectTimer);
        if (reconnectAttempts >= maxAutoReconnectAttempts) return;
        reconnectAttempts += 1;
        reconnectTimer = setTimeout(function () {
          reconnectTimer = null;
          if (listId && currentOnMessage) api.connect(listId, currentOnMessage, onStateChange);
        }, 3000);
      }

      if (typeof document !== 'undefined' && document.addEventListener) {
        document.addEventListener('visibilitychange', function () {
          if (document.visibilityState !== 'visible') return;
          if (!listId || !currentOnMessage) return;
          if (connectionState === 'connected') return;
          if (reconnectTimer) clearTimeout(reconnectTimer);
          reconnectTimer = null;
          reconnectAttempts = 0;
          if (ws) try { ws.close(); ws = null; } catch (e) {}
          api.connect(listId, currentOnMessage, onStateChange);
        });
      }

      var api = {
        connect: function (lid, onMessage, stateCallback) {
          if (ws && listId === lid && connectionState !== 'disconnected') return;
          listId = lid;
          currentOnMessage = onMessage;
          onStateChange = stateCallback || null;
          if (ws) try { ws.close(); } catch (e) {}
          ws = null;
          setState('connecting');
          var proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
          var url = proto + '//' + window.location.host + '/ws/list/' + lid + '/';
          ws = new WebSocket(url);
          ws.onopen = function () {
            reconnectAttempts = 0;
            setState('connected');
          };
          ws.onmessage = function (event) {
            try {
              var data = JSON.parse(event.data);
              $rootScope.$apply(function () { if (currentOnMessage) currentOnMessage(data); });
            } catch (e) {}
          };
          ws.onclose = function () {
            ws = null;
            setState('disconnected');
            tryReconnect();
          };
        },
        getConnectionState: function () { return connectionState; },
        reconnect: function () {
          if (reconnectTimer) clearTimeout(reconnectTimer);
          reconnectTimer = null;
          reconnectAttempts = 0;
          if (ws) try { ws.close(); ws = null; } catch (e) {}
          if (listId && currentOnMessage) api.connect(listId, currentOnMessage, onStateChange);
        },
        send: function (payload) {
          if (ws && ws.readyState === WebSocket.OPEN)
            ws.send(JSON.stringify(payload));
        },
        disconnect: function () {
          if (reconnectTimer) clearTimeout(reconnectTimer);
          reconnectTimer = null;
          reconnectAttempts = 0;
          listId = null;
          currentOnMessage = null;
          onStateChange = null;
          if (ws) try { ws.close(); ws = null; } catch (e) {}
          setState('disconnected');
        }
      };
      return api;
    });
})();
