// Reusable CDC tombstone filtering, lookback window, and deduplication helpers.

const VALID_IDENTIFIER_REGEX = /^[A-Za-z_][A-Za-z0-9_]*$/;
const VALID_LOOKBACK_DAYS_REGEX = /^[1-9][0-9]{0,3}$/;
const MAX_LOOKBACK_DAYS = 3650;
const DEFAULT_LOOKBACK_DAYS = "30";

function getVars() {
  if (
    typeof dataform !== "undefined" &&
    dataform.projectConfig &&
    dataform.projectConfig.vars
  ) {
    return dataform.projectConfig.vars;
  }
  return {};
}

function assertIdentifier(value, label) {
  if (typeof value !== "string") {
    throw new Error(`${label} must be a string.`);
  }
  if (!VALID_IDENTIFIER_REGEX.test(value)) {
    throw new Error(`Invalid SQL ${label} "${value}".`);
  }
  return value;
}

function filterCdcDeletes() {
  const vars = getVars();
  if (vars.filter_cdc_deletes === false) {
    return false;
  }
  if (
    typeof vars.filter_cdc_deletes === "string" &&
    vars.filter_cdc_deletes.trim().toLowerCase() === "false"
  ) {
    return false;
  }
  return true;
}

function activeCdcFilter(alias = "") {
  if (alias === undefined || alias === null) {
    alias = "";
  }
  if (typeof alias !== "string") {
    throw new Error("activeCdcFilter alias must be a string.");
  }

  let prefix = "";
  if (alias.length > 0) {
    if (!VALID_IDENTIFIER_REGEX.test(alias)) {
      throw new Error(
        `Invalid SQL table alias "${alias}" in activeCdcFilter.`
      );
    }
    prefix = `${alias}.`;
  }

  if (!filterCdcDeletes()) {
    return "TRUE";
  }
  return `COALESCE(${prefix}_metadata_deleted, FALSE) = FALSE`;
}

function parseLookbackDays(val) {
  let raw = val;
  if (typeof raw === "number" && Number.isInteger(raw)) {
    raw = String(raw);
  }
  if (typeof raw !== "string") {
    throw new Error(
      `Invalid cdc_lookback_days "${String(val)}". Expected integer between 1 and ${MAX_LOOKBACK_DAYS}.`
    );
  }
  const trimmed = raw.trim();
  if (!VALID_LOOKBACK_DAYS_REGEX.test(trimmed)) {
    throw new Error(
      `Invalid cdc_lookback_days "${val}". Expected integer between 1 and ${MAX_LOOKBACK_DAYS}.`
    );
  }
  const days = Number(trimmed);
  if (days < 1 || days > MAX_LOOKBACK_DAYS) {
    throw new Error(
      `cdc_lookback_days "${val}" out of range (1..${MAX_LOOKBACK_DAYS}).`
    );
  }
  return days;
}

function lookbackDays() {
  const vars = getVars();
  const raw =
    vars.cdc_lookback_days === undefined
      ? DEFAULT_LOOKBACK_DAYS
      : vars.cdc_lookback_days;
  return parseLookbackDays(raw);
}

function normalizeColumnList(columns, label) {
  if (Array.isArray(columns)) {
    if (columns.length === 0) {
      throw new Error(`${label} must contain at least one column.`);
    }
    return columns.map((col) => assertIdentifier(col, label));
  }
  if (typeof columns === "string" && columns.length > 0) {
    return [assertIdentifier(columns, label)];
  }
  throw new Error(`${label} must be a non-empty string or array.`);
}

function deduplicateCdc(
  keyColumns,
  orderColumns = ["_ingested_at", "_cdc_sequence_num"]
) {
  const keys = normalizeColumnList(keyColumns, "keyColumn");
  const orderCols = normalizeColumnList(orderColumns, "orderColumn");
  const orderClauses = orderCols.map((col) => `${col} DESC`);
  if (filterCdcDeletes()) {
    orderClauses.push("COALESCE(_metadata_deleted, FALSE) DESC");
  }
  return [
    "QUALIFY ROW_NUMBER() OVER (",
    `  PARTITION BY ${keys.join(", ")}`,
    `  ORDER BY ${orderClauses.join(", ")}`,
    ") = 1"
  ].join("\n");
}

module.exports = {
  filterCdcDeletes,
  activeCdcFilter,
  parseLookbackDays,
  lookbackDays,
  deduplicateCdc
};
