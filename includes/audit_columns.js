// Standard audit SQL expressions shared across Silver and Gold models.

const VALID_IDENTIFIER_REGEX = /^[A-Za-z_][A-Za-z0-9_]*$/;

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

function ingestedAtSql() {
  return "CURRENT_TIMESTAMP()";
}

function recordHashSql(columns) {
  if (!Array.isArray(columns) || columns.length === 0) {
    throw new Error("recordHashSql requires a non-empty column list.");
  }
  const fields = columns.map((col) => assertIdentifier(col, "column"));
  return `TO_HEX(SHA256(TO_JSON_STRING(STRUCT(${fields.join(", ")}))))`;
}

module.exports = {
  ingestedAtSql,
  recordHashSql
};
