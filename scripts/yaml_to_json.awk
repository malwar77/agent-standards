# yaml_to_json.awk - one standards YAML file -> one JSON object.
# Handles the block format written by agent_standards (and tolerates plain
# scalars). Pure awk, POSIX-safe (mawk included). sample_files are dropped.

function jstr(s) {
  gsub(/\\/, "\\\\", s)
  gsub(/"/, "\\\"", s)
  return "\"" s "\""
}

function flushstd(    ev) {
  if (id == "") return
  if (ev_has) {
    ev = "{\n      \"observed\": " (ev_observed + 0) ",\n" \
         "      \"followed\": " (ev_followed + 0) ",\n" \
         "      \"consistency\": " (ev_cons + 0) "\n    }"
  } else ev = "null"
  printf "  {\n"
  printf "    \"id\": %s,\n", jstr(id)
  printf "    \"title\": %s,\n", jstr(title)
  printf "    \"body\": %s,\n", jstr(body)
  printf "    \"category\": %s,\n", jstr(category)
  printf "    \"status\": %s,\n", jstr(status)
  printf "    \"critical\": %s,\n", (critical == "true" ? "true" : "false")
  printf "    \"source\": %s,\n", jstr(source)
  printf "    \"tags\": [%s],\n", tagsjson
  printf "    \"evidence\": %s\n", ev
  printf "  }"
}

{
  # any non-empty line at column 0 ends a body block
  if (inbody && $0 !~ /^ / && $0 !~ /^$/) inbody = 0
  if ($0 ~ /^id:/)    { flushstd(); id = substr($0, 5); title=""; body=""; category=""; status=""; source=""; critical="false"; tagsjson=""; ev_has=0; ev_observed=0; ev_followed=0; ev_cons=0; inbody=0; intags=0; inevid=0; next }
  if ($0 ~ /^title:/) { sub(/^title:[ ]+/, ""); title = $0; next }
  if ($0 ~ /^category:/) { sub(/^category:[ ]+/, ""); category = $0; next }
  if ($0 ~ /^status:/) { sub(/^status:[ ]+/, ""); status = $0; next }
  if ($0 ~ /^critical:/) { sub(/^critical:[ ]+/, ""); critical = $0; next }
  if ($0 ~ /^source:/) { sub(/^source:[ ]+/, ""); source = $0; next }
  if ($0 ~ /^tags:/) {
    v = $0; sub(/^tags:[ ]*/, "", v)
    if (v ~ /^\[/) {
      gsub(/^\[/, "", v); gsub(/\]$/, "", v)
      n = split(v, arr, ",")
      for (i = 1; i <= n; i++) {
        gsub(/^[ ]+|[ ]+$/, "", arr[i])
        tagsjson = tagsjson (tagsjson ? ", " : "") jstr(arr[i])
      }
    }
    intags = 1; next
  }
  if (intags && /^- /) {
    v = $0; sub(/^- /, "", v); gsub(/^[ ]+|[ ]+$/, "", v)
    tagsjson = tagsjson (tagsjson ? ", " : "") jstr(v)
    next
  }
  if (intags) intags = 0
  if ($0 ~ /^evidence:/) {
    v = $0; sub(/^evidence:[ ]*/, "", v)
    if (v != "null" && v != "~") { inevid = 1; ev_has = 1 }   # bare = map follows
    next
  }
  if (inevid && /^  [a-z_]+:/) {
    k = $0; sub(/^  /, "", k); split(k, kv, ":")
    val = kv[2]; gsub(/^[ ]+/, "", val)
    if (kv[1] == "observed") ev_observed = val
    if (kv[1] == "followed") ev_followed = val
    if (kv[1] == "consistency") ev_cons = val
    next
  }
  if (inevid && !/^ /) inevid = 0
  if ($0 ~ /^body:/) {
    b = $0; sub(/^body:[ ]+/, "", b)
    if (b == "|" || b == "|-") { inbody = 1; next }
    gsub(/^'/, "", b); gsub(/'$/, "", b)
    body = b; inbody = 0; next
  }
  if (inbody && /^  /) { sub(/^  /, ""); body = body (body ? " " : "") $0; next }
}

END { flushstd() }
