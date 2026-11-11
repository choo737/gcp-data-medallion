// Standard audit SQL expressions shared across Silver and Gold models.

function ingestedAtSql() {
  return "CURRENT_TIMESTAMP()";
}

function recordHashSql(columns) {
  if (!Array.isArray(columns) || columns.length === 0) {
    throw new Error("recordHashSql requires a non-empty column list.");
  }
  const fields = columns.map((col) => String(col).trim()).filter(Boolean);
  if (fields.length === 0) {
    throw new Error("recordHashSql requires valid column names.");
  }
  return `TO_HEX(SHA256(TO_JSON_STRING(STRUCT(${fields.join(", ")}))))`;
}

module.exports = {
  ingestedAtSql,
  recordHashSql
};
