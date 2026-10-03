package maat.threshold

# Generic quantitative gate: compares one numeric tool metric with a tier threshold.
pred := input.control.predicate

value := input.evidence[pred.tool].result.metrics[pred.metric]

has_value if is_number(value)

has_override if {
	_ = input.overrides[pred.threshold]
}

limit := input.overrides[pred.threshold]

limit := data.thresholds[input.tier][pred.threshold] if not has_override

has_limit if is_number(limit)

satisfied if {
	pred.op == "le"
	value <= limit
}

satisfied if {
	pred.op == "ge"
	value >= limit
}

satisfied if {
	pred.op == "eq"
	value == limit
}

active_waiver_ids contains w.id if {
	some w in input.waivers
	w.clause_id == input.control.id
	time.parse_rfc3339_ns(w.expiry) > input.as_of_ns
	not input.tier in input.control.non_waivable_at
}

msg := sprintf("%s=%v %s %v", [pred.metric, value, pred.op, limit])

default decision := {"outcome": "block", "reason": "no measured evidence"}

decision := {"outcome": "block", "reason": sprintf("no threshold %q configured for tier %q", [pred.threshold, input.tier])} if {
	has_value
	not has_limit
}

decision := {"outcome": "pass", "reason": msg} if {
	has_value
	has_limit
	satisfied
}

decision := {"outcome": "waive", "reason": concat("", ["violates ", msg, "; active waiver"]), "waiver_id": sort(active_waiver_ids)[0]} if {
	has_value
	has_limit
	not satisfied
	count(active_waiver_ids) > 0
}

decision := {"outcome": "block", "reason": concat("", ["violates ", msg])} if {
	has_value
	has_limit
	not satisfied
	count(active_waiver_ids) == 0
}
