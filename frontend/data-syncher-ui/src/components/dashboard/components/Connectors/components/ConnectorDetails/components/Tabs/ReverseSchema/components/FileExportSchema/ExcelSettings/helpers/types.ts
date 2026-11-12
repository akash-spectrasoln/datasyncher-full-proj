import {
  type ExcelBodyStyle,
  type ExcelConditionalFormat,
  type ExcelDifferentialStyle,
  type ExcelHeaderStyle,
  type ExcelOptions,
} from "@/types/connectors";

export type ColumnDataType = "numeric" | "datetime" | "boolean" | "text";

export const getColumnDataType = (
  typeStr: string | undefined,
): ColumnDataType => {
  if (!typeStr) return "text";
  const lower = typeStr.toLowerCase();
  if (
    lower.includes("number") ||
    lower.includes("int") ||
    lower.includes("float") ||
    lower.includes("double") ||
    lower.includes("decimal") ||
    lower.includes("numeric") ||
    lower.includes("real")
  ) {
    return "numeric";
  }
  if (
    lower.includes("date") ||
    lower.includes("time") ||
    lower.includes("timestamp")
  ) {
    return "datetime";
  }
  if (lower.includes("bool")) {
    return "boolean";
  }
  return "text";
};

export const stripFormulaQuotes = (val?: string): string => {
  if (!val) return "";
  const trimmed = String(val).trim();
  if (trimmed.startsWith('"') && trimmed.endsWith('"') && trimmed.length >= 2) {
    return trimmed.slice(1, -1).replace(/""/g, '"');
  }
  return val;
};

export interface ExcelSettingsProps {
  excelOptions: ExcelOptions | undefined;
  excelSheetName: string | undefined;
  conditionalFormats: ExcelConditionalFormat[] | undefined;
  tableFields: Record<string, string>;
  selectedFields?: string[] | null;
  tableName: string;
  onChange: (_patch: {
    excel_sheet_name?: string;
    excel_options?: ExcelOptions;
    excel_conditional_formats?: ExcelConditionalFormat[];
  }) => void;
}

export interface BasicOptionsTabProps {
  options: ExcelOptions;
  sheetName: string;
  colNames: string[];
  updateOptions: (_patch: Partial<ExcelOptions>) => void;
}

export interface SheetHeaderStyleSectionProps {
  options: ExcelOptions;
  sheetHeaderStyle: ExcelHeaderStyle;
  isSheetHeaderEnabled: boolean;
  updateOptions: (_patch: Partial<ExcelOptions>) => void;
  updateSheetHeaderStyle: (_patch: Partial<ExcelHeaderStyle>) => void;
}

export interface ColumnHeadersStyleSectionProps {
  headerStyle: ExcelHeaderStyle;
  updateHeaderStyle: (_patch: Partial<ExcelHeaderStyle>) => void;
}

export interface BodyStyleSectionProps {
  bodyStyle: ExcelBodyStyle;
  updateBodyStyle: (_patch: Partial<ExcelBodyStyle>) => void;
}

export interface StylingTabProps {
  options: ExcelOptions;
  headerStyle: ExcelHeaderStyle;
  sheetHeaderStyle: ExcelHeaderStyle;
  bodyStyle: ExcelBodyStyle;
  isSheetHeaderEnabled: boolean;
  updateOptions: (_patch: Partial<ExcelOptions>) => void;
  updateHeaderStyle: (_patch: Partial<ExcelHeaderStyle>) => void;
  updateSheetHeaderStyle: (_patch: Partial<ExcelHeaderStyle>) => void;
  updateBodyStyle: (_patch: Partial<ExcelBodyStyle>) => void;
}

export interface ConditionalFormattingTabProps {
  rules: ExcelConditionalFormat[];
  colNames: string[];
  tableFields: Record<string, string>;
  onAddRule: () => void;
  onUpdateRule: (
    _index: number,
    _patch: Partial<ExcelConditionalFormat>,
  ) => void;
  onUpdateRuleStyle: (
    _index: number,
    _patch: Partial<ExcelDifferentialStyle>,
  ) => void;
  onDeleteRule: (_e: React.MouseEvent, _index: number) => void;
}

export interface RuleCardProps {
  rule: ExcelConditionalFormat;
  index: number;
  totalRules: number;
  colNames: string[];
  tableFields: Record<string, string>;
  onUpdateRule: (
    _index: number,
    _patch: Partial<ExcelConditionalFormat>,
  ) => void;
  onUpdateRuleStyle: (
    _index: number,
    _patch: Partial<ExcelDifferentialStyle>,
  ) => void;
  onDeleteRule: (_e: React.MouseEvent, _index: number) => void;
}
