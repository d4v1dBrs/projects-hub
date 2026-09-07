(function (global) {
  "use strict";

  var GridStack = global.GridStack;
  if (!GridStack || !GridStack.Engine || !GridStack.Utils) return;

  var STORAGE_KEY = "bonos-dashboard-state-v1";
  var LEGACY_KEYS = ["grid-layout-v3", "panels-hidden-v1", "panel-cols-v2", "panel-cols-v1"];

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function positionsOverlap(left, right) {
    return !(left.y + left.h <= right.y || right.y + right.h <= left.y ||
             left.x + left.w <= right.x || right.x + right.w <= left.x);
  }

  function validateState(candidate, panelIds, columns) {
    if (!candidate || typeof candidate !== "object" || candidate.version !== 1 ||
        !Array.isArray(candidate.layout) || !Array.isArray(candidate.hidden) ||
        candidate.layout.length !== panelIds.length) return null;
    var known = new Set(panelIds);
    var seen = new Set();
    var layout = [];
    for (var index = 0; index < candidate.layout.length; index += 1) {
      var raw = candidate.layout[index];
      if (!raw || typeof raw !== "object" || !known.has(raw.id) || seen.has(raw.id)) return null;
      var numbers = [raw.x, raw.y, raw.w, raw.h];
      if (!numbers.every(Number.isInteger) || raw.x < 0 || raw.y < 0 ||
          raw.w < 1 || raw.h < 1 || raw.x + raw.w > columns) return null;
      seen.add(raw.id);
      layout.push({id: raw.id, x: raw.x, y: raw.y, w: raw.w, h: raw.h});
    }
    if (seen.size !== panelIds.length) return null;
    var hidden = new Set(candidate.hidden);
    if (hidden.size !== candidate.hidden.length) return null;
    for (var hiddenId of hidden) if (!seen.has(hiddenId)) return null;
    var visible = layout.filter(function (item) { return !hidden.has(item.id); });
    for (var left = 0; left < visible.length; left += 1) {
      for (var right = left + 1; right < visible.length; right += 1) {
        if (positionsOverlap(visible[left], visible[right])) return null;
      }
    }
    var byId = new Map(layout.map(function (item) { return [item.id, item]; }));
    return {
      version: 1,
      layout: panelIds.map(function (id) { return byId.get(id); }),
      hidden: panelIds.filter(function (id) { return hidden.has(id); }),
    };
  }

  class StableGridEngine extends GridStack.Engine {
    moveNode(node, options) {
      var proposed = Object.assign({}, node);
      GridStack.Utils.copyPos(proposed, options);
      this.nodeBoundFix(proposed, proposed.w !== node.w || proposed.h !== node.h);
      if (!options.nested && !options.skip && this.collide(node, proposed)) {
        var target = node._event && node._event.target ? node._event.target : node.el;
        if (target) target.dispatchEvent(new CustomEvent("dashboard:collision", {bubbles: true}));
        return false;
      }
      return super.moveNode(node, options);
    }
  }

  function createDashboardGrid(options) {
    var element = options.element;
    var columns = options.columns;
    var items = Array.prototype.slice.call(element.querySelectorAll("[gs-id]"));
    var panelIds = items.map(function (item) { return item.getAttribute("gs-id"); });
    var itemById = new Map(items.map(function (item) {
      return [item.getAttribute("gs-id"), item];
    }));
    var constraintsById = new Map(items.map(function (item) {
      var constraints = {};
      [
        ["minW", "gs-min-w"],
        ["minH", "gs-min-h"],
        ["maxW", "gs-max-w"],
        ["maxH", "gs-max-h"],
      ].forEach(function (entry) {
        var value = Number(item.getAttribute(entry[1]));
        if (Number.isInteger(value) && value > 0) constraints[entry[0]] = value;
      });
      return [item.getAttribute("gs-id"), constraints];
    }));
    var defaultState = validateState(options.defaultState, panelIds, columns);
    if (!defaultState) throw new Error("Invalid dashboard default state");

    LEGACY_KEYS.forEach(function (key) {
      try {
        localStorage.removeItem(key);
      } catch (error) {}
    });

    var initialState = defaultState;
    try {
      var storedState = validateState(
        JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"),
        panelIds,
        columns
      );
      if (storedState) initialState = storedState;
    } catch (error) {}

    if (!GridStack.Utils.__bonosResizeScrollDisabled) {
      GridStack.Utils.__bonosResizeScrollDisabled = true;
      GridStack.Utils.updateScrollResize = function () {};
    }

    var grid = GridStack.init({
      column: columns,
      cellHeight: options.cellHeight,
      margin: options.margin,
      float: true,
      animate: false,
      handle: ".layout-drag-handle",
      draggable: {scroll: false},
      resizable: {handles: "e, se"},
      engineClass: StableGridEngine,
    }, element);
    var positions = new Map();
    var hiddenPanels = new Set();
    var appliedState = clone(initialState);
    var draftState = clone(initialState);
    var editSnapshot = null;
    var editing = false;
    var replacing = false;
    var lastError = null;

    function positionFromNode(node) {
      return {id: node.id, x: node.x, y: node.y, w: node.w, h: node.h};
    }

    function syncVisiblePositions() {
      grid.engine.nodes.forEach(function (node) {
        positions.set(node.id, positionFromNode(node));
      });
    }

    function captureState() {
      syncVisiblePositions();
      return {
        version: 1,
        layout: panelIds.map(function (id) { return clone(positions.get(id)); }),
        hidden: panelIds.filter(function (id) { return hiddenPanels.has(id); }),
      };
    }

    function getState() {
      return clone(editing ? draftState : appliedState);
    }

    function emit(name) {
      element.dispatchEvent(new CustomEvent(name, {
        detail: {editing: editing, state: getState(), error: lastError},
      }));
    }

    function makeItemWidget(id, widgetOptions) {
      var item = itemById.get(id);
      grid.makeWidget(item, Object.assign({}, widgetOptions, constraintsById.get(id)));
      return item;
    }

    function replaceState(next, notify) {
      var normalized = validateState(next, panelIds, columns);
      if (!normalized) return false;
      var hidden = new Set(normalized.hidden);
      replacing = true;
      grid.batchUpdate();
      try {
        grid.removeAll(false, false);
        positions.clear();
        hiddenPanels.clear();
        normalized.layout.forEach(function (position) {
          positions.set(position.id, clone(position));
        });
        normalized.hidden.forEach(function (id) {
          hiddenPanels.add(id);
        });
        panelIds.forEach(function (id) {
          var item = itemById.get(id);
          if (hidden.has(id)) {
            item.hidden = true;
            return;
          }
          item.hidden = false;
          makeItemWidget(id, positions.get(id));
        });
      } finally {
        grid.batchUpdate(false);
        replacing = false;
      }
      syncVisiblePositions();
      draftState = captureState();
      if (notify !== false) emit("dashboard:statechange");
      return true;
    }

    function writeAppliedState(next) {
      try {
        if (JSON.stringify(next) === JSON.stringify(defaultState)) {
          localStorage.removeItem(STORAGE_KEY);
        } else {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        }
        return true;
      } catch (error) {
        return false;
      }
    }

    function beginEdit() {
      if (editing) return;
      editSnapshot = captureState();
      draftState = clone(editSnapshot);
      editing = true;
      lastError = null;
      grid.enable();
      element.classList.add("layout-editing");
      emit("dashboard:modechange");
    }

    function finishEdit() {
      editing = false;
      editSnapshot = null;
      draftState = clone(appliedState);
      lastError = null;
      grid.disable();
      element.classList.remove("layout-editing");
      emit("dashboard:modechange");
    }

    function cancelEdit() {
      if (!editing) return;
      replaceState(editSnapshot);
      finishEdit();
    }

    function applyEdit() {
      var next = validateState(captureState(), panelIds, columns);
      if (!next || !writeAppliedState(next)) {
        lastError = "No se pudo aplicar";
        emit("dashboard:applyerror");
        return false;
      }
      appliedState = clone(next);
      finishEdit();
      return true;
    }

    function previewDefault() {
      if (!editing) return false;
      return replaceState(defaultState);
    }

    function setPanelVisible(id, visible) {
      if (!editing || !itemById.has(id)) return false;
      var shouldShow = Boolean(visible);
      var isHidden = hiddenPanels.has(id);
      if (shouldShow === !isHidden) return true;
      var item = itemById.get(id);
      replacing = true;
      try {
        if (shouldShow) {
          var position = clone(positions.get(id));
          var widgetOptions = position;
          if (!grid.engine.isAreaEmpty(position.x, position.y, position.w, position.h)) {
            widgetOptions = Object.assign({}, position, {autoPosition: true});
          }
          hiddenPanels.delete(id);
          item.hidden = false;
          makeItemWidget(id, widgetOptions);
          positions.set(id, positionFromNode(item.gridstackNode));
        } else {
          positions.set(id, positionFromNode(item.gridstackNode));
          hiddenPanels.add(id);
          grid.removeWidget(item, false);
          item.hidden = true;
        }
      } finally {
        replacing = false;
      }
      draftState = captureState();
      emit("dashboard:statechange");
      return true;
    }

    function isPanelHidden(id) {
      return hiddenPanels.has(id);
    }

    function isEditing() {
      return editing;
    }

    replaceState(initialState, false);
    appliedState = clone(captureState());
    draftState = clone(appliedState);
    grid.on("change", function () {
      if (replacing) return;
      draftState = captureState();
      emit("dashboard:statechange");
    });
    grid.disable();
    element.classList.add("dashboard-ready");

    var controller = {
      grid: grid,
      beginEdit: beginEdit,
      applyEdit: applyEdit,
      cancelEdit: cancelEdit,
      previewDefault: previewDefault,
      setPanelVisible: setPanelVisible,
      isPanelHidden: isPanelHidden,
      isEditing: isEditing,
      getState: getState,
    };
    Object.defineProperty(controller, "lastError", {
      enumerable: true,
      get: function () { return lastError; },
    });
    return controller;
  }

  global.BonosDashboardGrid = {create: createDashboardGrid, validateState: validateState};
})(window);
