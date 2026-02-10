/**
 * AngularJS 1.8.2 SPA - Liste de courses
 * Routes: / (list selection), /list/:listId (list detail)
 */
(function () {
  'use strict';
  angular.module('listsApp', ['ngRoute'])
    .config(function ($routeProvider, $locationProvider) {
      $locationProvider.html5Mode(false);
      $routeProvider
        .when('/', {
          templateUrl: '/static/lists_app/partials/list-selection.html',
          controller: 'ListSelectionCtrl',
          controllerAs: 'vm'
        })
        .when('', {
          templateUrl: '/static/lists_app/partials/list-selection.html',
          controller: 'ListSelectionCtrl',
          controllerAs: 'vm'
        })
        .when('/list/:listId', {
          templateUrl: '/static/lists_app/partials/list-detail.html',
          controller: 'ListDetailCtrl',
          controllerAs: 'vm'
        })
        .otherwise({ redirectTo: '/' });
    });
})();
