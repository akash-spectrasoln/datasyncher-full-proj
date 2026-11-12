import { type ExcelConditionItem } from "@/types/connectors";

import { getColumnDataType, stripFormulaQuotes } from "./types";

export interface ConditionRuleItem {
  id: string;
  type: "rule";
  column: string;
  operator: string;
  value: string;
  value2?: string;
}

export interface ConditionRuleGroup {
  id: string;
  type: "group";
  conjunction: "and" | "or";
  children: Array<ConditionRuleItem | ConditionRuleGroup>;
}

export type ConditionRuleNode = ConditionRuleItem | ConditionRuleGroup;

let idSeed = 1000;
export const generateId = (prefix = "node"): string => {
  return `${prefix}-${++idSeed}`;
};

export const createRule = (
  id?: string,
  column = "",
  operator = "equal",
  value = "",
  value2?: string,
): ConditionRuleItem => ({
  id: id || generateId("r"),
  type: "rule",
  column,
  operator,
  value,
  ...(value2 !== undefined ? { value2 } : {}),
});

export const createGroup = (
  id?: string,
  conjunction: "and" | "or" = "and",
  children: ConditionRuleNode[] = [],
): ConditionRuleGroup => ({
  id: id || generateId("g"),
  type: "group",
  conjunction,
  children,
});

export const cloneTree = (group: ConditionRuleGroup): ConditionRuleGroup => {
  return {
    ...group,
    children: group.children.map((child) =>
      child.type === "rule" ? { ...child } : cloneTree(child),
    ),
  };
};

export interface NodeLocation {
  node: ConditionRuleNode;
  parent: ConditionRuleGroup | null;
  index: number;
  depth: number;
}

export const findNodeAndParent = (
  current: ConditionRuleGroup,
  targetId: string,
  parent: ConditionRuleGroup | null = null,
  depth = 0,
): NodeLocation | null => {
  if (current.id === targetId) {
    return {
      node: current,
      parent,
      index: parent ? parent.children.findIndex((c) => c.id === targetId) : 0,
      depth,
    };
  }

  for (let i = 0; i < current.children.length; i++) {
    const child = current.children[i];
    if (child.id === targetId) {
      return { node: child, parent: current, index: i, depth: depth + 1 };
    }
    if (child.type === "group") {
      const found = findNodeAndParent(child, targetId, current, depth + 1);
      if (found) return found;
    }
  }

  return null;
};

export interface CommonParentResult {
  valid: boolean;
  parentGroup: ConditionRuleGroup | null;
  parentDepth: number;
  reason?: string;
}

export const findCommonParent = (
  tree: ConditionRuleGroup,
  selectedIds: string[],
): CommonParentResult => {
  if (selectedIds.length < 2) {
    return {
      valid: false,
      parentGroup: null,
      parentDepth: 0,
      reason: "Select at least 2 conditions to group",
    };
  }

  const locations = selectedIds.map((id) => findNodeAndParent(tree, id));
  if (locations.some((loc) => !loc || !loc.parent)) {
    return {
      valid: false,
      parentGroup: null,
      parentDepth: 0,
      reason: "Invalid selection: could not locate all selected conditions",
    };
  }

  const firstParentId = locations[0]!.parent!.id;
  const sameParent = locations.every(
    (loc) => loc!.parent && loc!.parent.id === firstParentId,
  );

  if (!sameParent) {
    return {
      valid: false,
      parentGroup: null,
      parentDepth: 0,
      reason: "Selected conditions must belong to the same level",
    };
  }

  return {
    valid: true,
    parentGroup: locations[0]!.parent,
    parentDepth: locations[0]!.depth - 1,
  };
};

export const groupSelectedNodes = (
  tree: ConditionRuleGroup,
  selectedIds: string[],
  maxDepth = 3,
): ConditionRuleGroup => {
  const common = findCommonParent(tree, selectedIds);
  if (!common.valid || !common.parentGroup) {
    return tree;
  }

  if (common.parentDepth + 1 >= maxDepth) {
    return tree;
  }

  const nextTree = cloneTree(tree);
  const parentLoc = findNodeAndParent(nextTree, common.parentGroup.id);
  if (!parentLoc || parentLoc.node.type !== "group") {
    return tree;
  }

  const targetGroup = parentLoc.node as ConditionRuleGroup;
  const idSet = new Set(selectedIds);

  const selectedChildren: ConditionRuleNode[] = [];
  const remainingChildren: ConditionRuleNode[] = [];
  let insertIndex = -1;

  for (let i = 0; i < targetGroup.children.length; i++) {
    const child = targetGroup.children[i];
    if (idSet.has(child.id)) {
      if (insertIndex === -1) {
        insertIndex = remainingChildren.length;
      }
      selectedChildren.push(child);
    } else {
      remainingChildren.push(child);
    }
  }

  if (selectedChildren.length < 2) {
    return tree;
  }

  const newConjunction: "and" | "or" =
    targetGroup.conjunction === "and" ? "or" : "and";

  const newGroup: ConditionRuleGroup = {
    id: generateId("g"),
    type: "group",
    conjunction: newConjunction,
    children: selectedChildren,
  };

  const finalChildren = [
    ...remainingChildren.slice(0, insertIndex),
    newGroup,
    ...remainingChildren.slice(insertIndex),
  ];

  targetGroup.children = finalChildren;
  return nextTree;
};

export const ungroupNode = (
  tree: ConditionRuleGroup,
  groupId: string,
): ConditionRuleGroup => {
  if (tree.id === groupId) {
    return tree;
  }

  const nextTree = cloneTree(tree);
  const loc = findNodeAndParent(nextTree, groupId);
  if (!loc || !loc.parent || loc.node.type !== "group") {
    return tree;
  }

  const parent = loc.parent;
  const group = loc.node as ConditionRuleGroup;
  const idx = loc.index;

  parent.children.splice(idx, 1, ...group.children);
  return nextTree;
};

export const cleanHierarchy = (
  group: ConditionRuleGroup,
): ConditionRuleGroup => {
  const cleanedChildren: ConditionRuleNode[] = [];

  for (const child of group.children) {
    if (child.type === "rule") {
      cleanedChildren.push(child);
    } else {
      const cleanedChildGroup = cleanHierarchy(child);
      if (cleanedChildGroup.children.length === 0) {
        continue;
      } else if (cleanedChildGroup.children.length === 1) {
        const singleChild = cleanedChildGroup.children[0];
        if (singleChild.type === "rule") {
          cleanedChildren.push(singleChild);
        } else {
          cleanedChildren.push(...cleanHierarchy(singleChild).children);
        }
      } else {
        cleanedChildren.push(cleanedChildGroup);
      }
    }
  }

  group.children = cleanedChildren;
  return group;
};

export const deleteNode = (
  tree: ConditionRuleGroup,
  targetId: string,
): ConditionRuleGroup => {
  const nextTree = cloneTree(tree);

  if (nextTree.id === targetId) {
    return createGroup("root", "and", [createRule()]);
  }

  const loc = findNodeAndParent(nextTree, targetId);
  if (!loc || !loc.parent) {
    return tree;
  }

  loc.parent.children.splice(loc.index, 1);
  cleanHierarchy(nextTree);

  if (nextTree.children.length === 0) {
    nextTree.children.push(createRule());
  }

  return nextTree;
};

export const addRuleToGroup = (
  tree: ConditionRuleGroup,
  groupId: string,
): ConditionRuleGroup => {
  const nextTree = cloneTree(tree);
  if (nextTree.id === groupId) {
    nextTree.children.push(createRule());
    return nextTree;
  }

  const loc = findNodeAndParent(nextTree, groupId);
  if (loc && loc.node.type === "group") {
    (loc.node as ConditionRuleGroup).children.push(createRule());
  }
  return nextTree;
};

export const toggleGroupConjunction = (
  tree: ConditionRuleGroup,
  groupId: string,
): ConditionRuleGroup => {
  const nextTree = cloneTree(tree);
  const loc = findNodeAndParent(nextTree, groupId);
  const group =
    nextTree.id === groupId
      ? nextTree
      : loc && loc.node.type === "group"
        ? (loc.node as ConditionRuleGroup)
        : null;

  if (!group || group.type !== "group") {
    return tree;
  }

  group.conjunction = group.conjunction === "and" ? "or" : "and";
  return nextTree;
};

/**
 * Toggles conjunction at a specific inter-row divider between
 * children[childIndex - 1] and children[childIndex] in parentGroupId.
 *
 * If parent has 2 children, simply toggles parent.conjunction.
 * If parent has > 2 children, isolates this toggle to this specific divider
 * by grouping adjacent children on either side with the parent's current conjunction,
 * and setting parent.conjunction to the toggled conjunction.
 */
export const toggleDividerConjunction = (
  tree: ConditionRuleGroup,
  parentGroupId: string,
  childIndex: number,
): ConditionRuleGroup => {
  const nextTree = cloneTree(tree);
  const loc = findNodeAndParent(nextTree, parentGroupId);
  const parent =
    nextTree.id === parentGroupId
      ? nextTree
      : loc && loc.node.type === "group"
        ? (loc.node as ConditionRuleGroup)
        : null;

  if (
    !parent ||
    parent.type !== "group" ||
    childIndex <= 0 ||
    childIndex >= parent.children.length
  ) {
    return tree;
  }

  if (parent.children.length === 2) {
    parent.conjunction = parent.conjunction === "and" ? "or" : "and";
    return nextTree;
  }

  const currentConj = parent.conjunction;
  const targetConj = currentConj === "and" ? "or" : "and";

  const leftItems = parent.children.slice(0, childIndex);
  const rightItems = parent.children.slice(childIndex);

  const leftChild: ConditionRuleNode =
    leftItems.length === 1
      ? leftItems[0]
      : createGroup(generateId("g"), currentConj, leftItems);

  const rightChild: ConditionRuleNode =
    rightItems.length === 1
      ? rightItems[0]
      : createGroup(generateId("g"), currentConj, rightItems);

  parent.children = [leftChild, rightChild];
  parent.conjunction = targetConj;

  return nextTree;
};

// Converts flat ExcelConditionItem[] into a tree of ConditionRuleGroup using a bracket stack
export const conditionsToTree = (
  conditions: ExcelConditionItem[] | undefined,
): ConditionRuleGroup => {
  if (!conditions || conditions.length === 0) {
    return createGroup("root", "and", [createRule()]);
  }

  const root = createGroup("root", "and", []);
  const stack: ConditionRuleGroup[] = [root];

  conditions.forEach((c, idx) => {
    const numOpen = (c.open_paren || "").split("(").length - 1;
    const numClose = (c.close_paren || "").split(")").length - 1;

    // Open any new groups on this row
    for (let o = 0; o < numOpen; o++) {
      const parent = stack[stack.length - 1];
      if (parent.children.length > 0 && c.logic) {
        parent.conjunction = c.logic.startsWith("or") ? "or" : "and";
      }
      const defaultConjunction = parent.conjunction === "and" ? "or" : "and";
      const newGroup = createGroup(`g-${idx}-${o}`, defaultConjunction, []);
      parent.children.push(newGroup);
      stack.push(newGroup);
    }

    const rule = createRule(
      `r-${idx}`,
      c.column || "",
      c.operator || "equal",
      c.value ?? "",
      c.value2,
    );

    const targetGroup = stack[stack.length - 1];
    if (targetGroup.children.length > 0 && c.logic) {
      targetGroup.conjunction = c.logic.startsWith("or") ? "or" : "and";
    }
    targetGroup.children.push(rule);

    // Close any groups ending on this row
    for (let cl = 0; cl < numClose; cl++) {
      if (stack.length > 1) {
        stack.pop();
      }
    }
  });

  cleanHierarchy(root);
  if (root.children.length === 0) {
    root.children.push(createRule());
  }

  return root;
};

// Serializes ConditionRuleGroup into flat ExcelConditionItem[] accumulating multiple parens
export const treeToConditions = (
  tree: ConditionRuleGroup,
): ExcelConditionItem[] => {
  const result: ExcelConditionItem[] = [];
  let isFirstOverall = true;

  const serializeNode = (
    node: ConditionRuleNode,
    inheritedLogic: "and" | "or",
  ) => {
    if (node.type === "rule") {
      const item: ExcelConditionItem = {
        column: node.column,
        operator: node.operator,
        value: node.value,
        ...(node.value2 !== undefined ? { value2: node.value2 } : {}),
      };
      if (!isFirstOverall) {
        item.logic = inheritedLogic;
      }
      isFirstOverall = false;
      result.push(item);
    } else {
      const children = node.children;
      if (children.length === 0) return;

      const groupLogic = node.conjunction;
      const startIndex = result.length;

      for (let i = 0; i < children.length; i++) {
        const child = children[i];
        const effectiveLogic = i === 0 ? inheritedLogic : groupLogic;
        serializeNode(child, effectiveLogic);
      }

      const endIndex = result.length - 1;
      // Mark open paren on first row of this group (ACCUMULATING so multiple groups on same row get "((")
      if (startIndex < result.length) {
        result[startIndex].open_paren =
          (result[startIndex].open_paren || "") + "(";
      }
      // Mark close paren on last row of this group (ACCUMULATING so multiple groups on same row get "))")
      if (endIndex >= startIndex && endIndex >= 0) {
        result[endIndex].close_paren =
          (result[endIndex].close_paren || "") + ")";
      }
    }
  };

  for (let i = 0; i < tree.children.length; i++) {
    serializeNode(tree.children[i], tree.conjunction);
  }

  if (result.length === 0) {
    return [{ column: "", operator: "equal", value: "" }];
  }

  return result;
};

// Formats a rule value for display in human-readable summary, matching Excel conventions:
// - Numbers: unquoted (e.g. 5, 400)
// - Booleans: unquoted (e.g. TRUE, FALSE)
// - Formulas / cell refs starting with '=': unquoted (e.g. =TODAY(), =A1)
// - Strings / text: quoted with double quotes (e.g. "Pending")
export const formatRuleValueForSummary = (
  val: string | undefined,
  colName: string,
  tableFields?: Record<string, unknown>,
): string => {
  if (val === undefined || val === null) return "";
  let trimmed = String(val).trim();
  if (trimmed === "") return '""';

  // Strip formula quotes or outer quotes if already wrapped
  trimmed = stripFormulaQuotes(trimmed);
  if (trimmed.startsWith("'") && trimmed.endsWith("'") && trimmed.length >= 2) {
    trimmed = trimmed.slice(1, -1);
  }

  // Formula or cell reference starting with '=' -> keep bare
  if (trimmed.startsWith("=")) {
    return trimmed;
  }

  const rawType = tableFields ? tableFields[colName] : undefined;
  const typeRecord =
    typeof rawType === "object" && rawType !== null
      ? (rawType as Record<string, unknown>)
      : undefined;
  const typeStr = typeRecord
    ? (typeof typeRecord.data_type === "string"
        ? typeRecord.data_type
        : undefined) ||
      (typeof typeRecord.type === "string" ? typeRecord.type : undefined)
    : typeof rawType === "string"
      ? rawType
      : undefined;
  const colDataType = getColumnDataType(typeStr);

  // Booleans in Excel: TRUE / FALSE without quotes
  const isBool =
    colDataType === "boolean" ||
    trimmed.toUpperCase() === "TRUE" ||
    trimmed.toUpperCase() === "FALSE";

  if (isBool) {
    return trimmed.toUpperCase();
  }

  // Numbers in Excel: without quotes
  const isNum =
    colDataType === "numeric"
      ? !isNaN(Number(trimmed)) && trimmed !== ""
      : !isNaN(Number(trimmed)) && trimmed !== "" && !trimmed.includes(" ");

  if (isNum) {
    return trimmed;
  }

  // Text strings in Excel: wrapped in double quotes, escaping internal quotes
  return `"${trimmed.replace(/"/g, '""')}"`;
};

// Formats a ConditionRuleNode into clean human-readable text directly from the tree structure
export const nodeToHumanSummary = (
  node: ConditionRuleNode,
  tableFields?: Record<string, string>,
  isRoot = true,
): string => {
  if (node.type === "rule") {
    if (!node.column) return "";

    if (node.operator === "isEmpty") return `${node.column} is empty`;
    if (node.operator === "isNotEmpty") return `${node.column} is not empty`;
    if (node.operator === "between") {
      const v1 = node.value
        ? formatRuleValueForSummary(node.value, node.column, tableFields)
        : "?";
      const v2 = node.value2
        ? formatRuleValueForSummary(node.value2, node.column, tableFields)
        : "?";
      return `${node.column} between ${v1} and ${v2}`;
    }
    if (node.operator === "notBetween") {
      const v1 = node.value
        ? formatRuleValueForSummary(node.value, node.column, tableFields)
        : "?";
      const v2 = node.value2
        ? formatRuleValueForSummary(node.value2, node.column, tableFields)
        : "?";
      return `${node.column} not between ${v1} and ${v2}`;
    }

    let op = "=";
    if (node.operator === "notEqual") op = "!=";
    if (node.operator === "greaterThan") op = ">";
    if (node.operator === "lessThan") op = "<";
    if (node.operator === "greaterThanOrEqual") op = ">=";
    if (node.operator === "lessThanOrEqual") op = "<=";
    if (node.operator === "contains") op = "contains";
    if (node.operator === "notContains") op = "does not contain";
    if (node.operator === "beginsWith") op = "starts with";
    if (node.operator === "notBeginsWith") op = "does not start with";
    if (node.operator === "endsWith") op = "ends with";
    if (node.operator === "notEndsWith") op = "does not end with";

    const formattedVal = formatRuleValueForSummary(
      node.value,
      node.column,
      tableFields,
    );
    return `${node.column} ${op} ${formattedVal}`;
  }

  const parts = node.children
    .map((c) => nodeToHumanSummary(c, tableFields, false))
    .filter(Boolean);

  if (parts.length === 0) return "";
  if (parts.length === 1) return parts[0];

  const joined = parts.join(` ${node.conjunction.toUpperCase()} `);
  return isRoot ? joined : `(${joined})`;
};
