// Reusable CDC tombstone filtering helpers for Bronze-to-Silver models.

const VALID_ALIAS_REGEX = /^[A-Za-z_][A-Za-z0-9_]*$/;

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
    if (!VALID_ALIAS_REGEX.test(alias)) {
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

module.exports = {
  filterCdcDeletes,
  activeCdcFilter
};
