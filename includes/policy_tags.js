// Column governance helper for optional BigQuery PII policy tags.

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

function getPiiPolicyTag() {
  const vars = getVars();
  return typeof vars.pii_policy_tag === "string"
    ? vars.pii_policy_tag.trim()
    : "";
}

function allowUntaggedPii() {
  const vars = getVars();
  if (vars.allow_untagged_pii === false || vars.allow_untagged_pii === "false") {
    return false;
  }
  return true;
}

function piiColumnConfig(description) {
  const tag = getPiiPolicyTag();
  if (tag.length > 0) {
    return {
      description: description,
      bigqueryPolicyTags: [tag]
    };
  }
  if (!allowUntaggedPii()) {
    throw new Error(
      "pii_policy_tag is required when allow_untagged_pii is false."
    );
  }
  return {
    description: description
  };
}

module.exports = {
  getPiiPolicyTag,
  allowUntaggedPii,
  piiColumnConfig
};
