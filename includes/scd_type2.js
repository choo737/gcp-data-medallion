// Reusable SCD Type 2 window and change-detection helpers for CDC streams.

const VALID_IDENTIFIER_REGEX = /^[A-Za-z_][A-Za-z0-9_]*$/;
const VALID_RELATION_REGEX =
  /^(?:[A-Za-z_][A-Za-z0-9_]*|`[A-Za-z0-9_-]+\.[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*`)$/;
const VALID_TIMESTAMP_LITERAL_REGEX =
  /^TIMESTAMP\('(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})? UTC)'\)$/;
const VALID_ISO_UTC_REGEX =
  /^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})? UTC)$/;

function assertIdentifier(value, label) {
  if (typeof value !== "string") {
    throw new Error(`${label} must be a string identifier.`);
  }
  const trimmed = value.trim();
  if (!VALID_IDENTIFIER_REGEX.test(trimmed)) {
    throw new Error(`Invalid SQL identifier "${value}" for ${label}.`);
  }
  return trimmed;
}

function normalizeOpenEndSql(openEndSql) {
  if (openEndSql === undefined || openEndSql === null || openEndSql === "") {
    return null;
  }
  if (typeof openEndSql !== "string") {
    throw new Error("openEndSql must be a UTC timestamp literal string.");
  }
  const trimmed = openEndSql.trim();
  const tsMatch = VALID_TIMESTAMP_LITERAL_REGEX.exec(trimmed);
  if (tsMatch) {
    return `TIMESTAMP('${tsMatch[1]}')`;
  }
  const isoMatch = VALID_ISO_UTC_REGEX.exec(trimmed);
  if (isoMatch) {
    return `TIMESTAMP('${isoMatch[1]}')`;
  }
  throw new Error(
    `Invalid openEndSql "${openEndSql}". Expected TIMESTAMP('YYYY-MM-DD HH:MM:SS UTC').`
  );
}

function normalizeKeys(naturalKey) {
  if (Array.isArray(naturalKey)) {
    if (naturalKey.length === 0) {
      throw new Error("naturalKey must contain at least one column.");
    }
    return naturalKey.map((key) => assertIdentifier(key, "naturalKey"));
  }
  if (typeof naturalKey === "string" && naturalKey.trim().length > 0) {
    return [assertIdentifier(naturalKey, "naturalKey")];
  }
  throw new Error("naturalKey must be a non-empty string or array.");
}

function normalizeOrderColumns(orderByColumns) {
  if (Array.isArray(orderByColumns)) {
    if (orderByColumns.length === 0) {
      throw new Error("orderByColumn must contain at least one column.");
    }
    return orderByColumns.map((col) => assertIdentifier(col, "orderByColumn"));
  }
  if (typeof orderByColumns === "string" && orderByColumns.trim().length > 0) {
    return [assertIdentifier(orderByColumns, "orderByColumn")];
  }
  throw new Error("orderByColumn must be a non-empty string or array.");
}

function scd2PreviousHashSql(
  naturalKey,
  orderByColumns,
  hashColumn = "record_hash"
) {
  const keys = normalizeKeys(naturalKey).join(", ");
  const orderCols = normalizeOrderColumns(orderByColumns);
  const safeHashCol = assertIdentifier(hashColumn, "hashColumn");
  const orderByClause = orderCols.map((col) => `${col} ASC`).join(", ");
  return `LAG(${safeHashCol}) OVER (PARTITION BY ${keys} ORDER BY ${orderByClause})`;
}

function scd2WindowColumnsSql(naturalKey, orderByColumns, openEndSql) {
  const orderCols = normalizeOrderColumns(orderByColumns);
  const primaryOrderCol = orderCols[0];
  const orderByClause = orderCols.map((col) => `${col} ASC`).join(", ");
  const keys = normalizeKeys(naturalKey).join(", ");
  const safeOpenEnd = normalizeOpenEndSql(openEndSql);
  const nextExpr = `LEAD(${primaryOrderCol}) OVER (PARTITION BY ${keys} ORDER BY ${orderByClause})`;
  const validToExpr = safeOpenEnd
    ? `COALESCE(${nextExpr}, ${safeOpenEnd})`
    : nextExpr;
  return [
    `${primaryOrderCol} AS valid_from`,
    `${validToExpr} AS valid_to`,
    `CASE WHEN ${nextExpr} IS NULL THEN TRUE ELSE FALSE END AS is_current`
  ].join(",\n  ");
}

function buildScd2Query(options) {
  const {
    sourceSql,
    naturalKey,
    orderByColumn,
    columns,
    openEndSql = "TIMESTAMP('9999-12-31 23:59:59 UTC')",
    excludeDeletedColumn = ""
  } = options || {};

  if (
    typeof sourceSql !== "string" ||
    !VALID_RELATION_REGEX.test(sourceSql.trim())
  ) {
    throw new Error(
      "buildScd2Query requires a valid CTE or backtick-quoted relation in sourceSql."
    );
  }
  if (!Array.isArray(columns) || columns.length === 0) {
    throw new Error(
      "buildScd2Query requires an explicit non-empty columns list."
    );
  }
  const safeSource = sourceSql.trim();
  const projected = columns.map((col) => assertIdentifier(col, "column"));
  let filterClause = "";
  if (
    excludeDeletedColumn !== undefined &&
    excludeDeletedColumn !== null &&
    excludeDeletedColumn !== ""
  ) {
    const delCol = assertIdentifier(
      excludeDeletedColumn,
      "excludeDeletedColumn"
    );
    filterClause = `\nWHERE COALESCE(${delCol}, FALSE) = FALSE`;
  }

  return [
    "SELECT",
    `  ${projected.join(",\n  ")},`,
    `  ${scd2WindowColumnsSql(naturalKey, orderByColumn, openEndSql)}`,
    `FROM ${safeSource}${filterClause}`
  ].join("\n");
}

module.exports = {
  normalizeKeys,
  normalizeOrderColumns,
  scd2PreviousHashSql,
  scd2WindowColumnsSql,
  buildScd2Query
};
