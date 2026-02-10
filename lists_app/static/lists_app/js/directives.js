/**
 * Swipe-to-reveal directive (iOS-style) for list row: Archive and Delete buttons.
 */
(function () {
  'use strict';
  angular.module('listsApp')
    .directive('swipeReveal', function ($parse) {
      return {
        restrict: 'A',
        scope: true,
        link: function (scope, el, attrs) {
          var content = el[0].querySelector('.swipe-content');
          var actions = el[0].querySelector('.swipe-actions');
          if (!content || !actions) return;
          var fnArchive = attrs.onArchive ? $parse(attrs.onArchive) : angular.noop;
          var fnRestore = attrs.onRestore ? $parse(attrs.onRestore) : angular.noop;
          var fnDelete = attrs.onDelete ? $parse(attrs.onDelete) : angular.noop;
          var startX = 0;
          var currentX = 0;
          var actionWidth = actions.offsetWidth || 200;
          content.addEventListener('touchstart', function (e) {
            startX = e.touches[0].clientX;
          }, { passive: true });
          content.addEventListener('touchmove', function (e) {
            currentX = e.touches[0].clientX - startX;
            if (currentX > 0) currentX = 0;
            if (currentX < -actionWidth) currentX = -actionWidth;
            content.style.transform = 'translateX(' + currentX + 'px)';
          }, { passive: true });
          content.addEventListener('touchend', function () {
            if (currentX < -actionWidth / 2) {
              content.style.transform = 'translateX(-' + actionWidth + 'px)';
              scope.swipeOpen = true;
            } else {
              content.style.transform = 'translateX(0)';
              scope.swipeOpen = false;
            }
            scope.$apply();
          });
          scope.doArchive = function () {
            content.style.transform = 'translateX(0)';
            fnArchive(scope);
          };
          scope.doRestore = function () {
            content.style.transform = 'translateX(0)';
            fnRestore(scope);
          };
          scope.doDelete = function () {
            content.style.transform = 'translateX(0)';
            fnDelete(scope);
          };
        }
      };
    })
    .directive('sortableItems', function () {
      return {
        restrict: 'A',
        scope: { section: '=', onReorder: '&' },
        link: function (scope, el, attrs) {
          if (typeof Sortable === 'undefined') return;
          var sortable = new Sortable(el[0], {
            animation: 150,
            handle: '.sort-handle',
            dataIdAttr: 'data-item-id',
            onEnd: function (evt) {
              var ids = sortable.toArray();
              scope.$apply(function () {
                scope.onReorder({ section: scope.section, itemIds: ids });
              });
            }
          });
        }
      };
    });
})();
