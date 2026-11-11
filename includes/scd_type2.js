// Reusable SCD Type 2 window helpers for CDC streams.

function normalizeKeys(naturalKey) {
  if (Array.isArray(naturalKey)) {
    const cleaned = naturalKey.map((key) => String(key).trim()).filter(Boolean);
    if (cleaned.length === 0) {
      throw new Error("naturalKey must contain at least one column.");
    }
    return cleaned;
  }
  if (typeof naturalKey === "string" && naturalKey.trim().length > 0) {
    return [naturalKey.trim()];
  }
  throw new Error("naturalKey must be a non-empty string or array.");
}

function scd2WindowColumnsSql(naturalKey, orderByColumn, openEndSql) {
  if (typeof orderByColumn !== "string" || orderByColumn.trim().length === 0) {
    throw new Error("orderByColumn must be a non-empty column name.");
  }
  const orderCol = orderByColumn.trim();
  const keys = normalizeKeys(naturalKey).join(", ");
  const nextExpr = `LEAD(${orderCol}) OVER (PARTITION BY ${keys} ORDER BY ${orderCol} ASC)`;
  const validToExpr = openEndSql
    ? `COALESCE(${nextExpr}, ${openEndSql})`
    : nextExpr;
  return [
    `${orderCol} AS valid_from`,
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
    whereSql = ""
  } = options || {};

  if (!sourceSql || !Array.isArray(columns) || columns.length === 0) {
    throw new Error("buildScd2Query requires sourceSql and an explicit columns list.");
  }
  const projected = columns.map((col) => String(col).trim()).filter(Boolean);
  if (projected.length === 0) {
    throw new Error("buildScd2Query requires valid column names.");
  }
  const filterClause =
    whereSql && whereSql.trim().length > 0 ? `\nWHERE ${whereSql.trim()}` : "";

  return [
    "SELECT",
    `  ${projected.join(",\n  ")},`,
    `  ${scd2WindowColumnsSql(naturalKey, orderByColumn, openEndSql)}`,
    `FROM ${sourceSql}${filterClause}`
  ].join("\n");
}

module.exports = {
  normalizeKeys,
  scd2WindowColumnsSql,
  buildScd2Query
};
