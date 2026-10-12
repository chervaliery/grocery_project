/**
 * AngularJS 1.8.2 SPA - Liste de courses
 * Routes: / (list selection), /list/:listId (list detail)
 */
(function () {
  'use strict';
  var v = window.ASSET_VERSION ? '?v=' + window.ASSET_VERSION : '';
  angular.module('listsApp', ['ngRoute'])
    .config(function ($routeProvider, $locationProvider) {
      $locationProvider.html5Mode(false);
      $routeProvider
        .when('/', {
          templateUrl: '/static/lists_app/partials/list-selection.html' + v,
          controller: 'ListSelectionCtrl',
          controllerAs: 'vm'
        })
        .when('', {
          templateUrl: '/static/lists_app/partials/list-selection.html' + v,
          controller: 'ListSelectionCtrl',
          controllerAs: 'vm'
        })
        .when('/list/:listId', {
          templateUrl: '/static/lists_app/partials/list-detail.html' + v,
          controller: 'ListDetailCtrl',
          controllerAs: 'vm'
        })
        .otherwise({ redirectTo: '/' });
    });
})();
