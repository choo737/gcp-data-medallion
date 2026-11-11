// Column governance helper for optional BigQuery PII policy tags.

function getPiiPolicyTag() {
  if (
    typeof dataform !== "undefined" &&
    dataform.projectConfig &&
    dataform.projectConfig.vars &&
    typeof dataform.projectConfig.vars.pii_policy_tag === "string"
  ) {
    return dataform.projectConfig.vars.pii_policy_tag.trim();
  }
  return "";
}

function piiColumnConfig(description) {
  const tag = getPiiPolicyTag();
  if (tag.length > 0) {
    return {
      description: description,
      bigqueryPolicyTags: [tag]
    };
  }
  return {
    description: description
  };
}

module.exports = {
  getPiiPolicyTag,
  piiColumnConfig
};
