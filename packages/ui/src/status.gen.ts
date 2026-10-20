// GENERATED from docs/product/status-vocabulary.yaml. Do not edit.
// Regenerate: python -m abacus_tools.codegen.status_vocabulary (C2; F-03-T09).

export const STATUS_REGISTRY = {
  "engagement": {
    "prospect": {
      "label": "Prospect",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "accepted": {
      "label": "Accepted",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "declined": {
      "label": "Declined",
      "variant": "soon",
      "terminal": true,
      "derived": false
    },
    "contracted": {
      "label": "Letter signed",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "active": {
      "label": "Active",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "on_hold": {
      "label": "On hold",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "delivered": {
      "label": "Delivered",
      "variant": "green",
      "terminal": false,
      "derived": false
    },
    "archived": {
      "label": "Archived",
      "variant": "soon",
      "terminal": true,
      "derived": false,
      "contextLabels": {
        "with_lock_icon": "Archived"
      }
    }
  },
  "return": {
    "not_started": {
      "label": "Not started",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "gathering": {
      "label": "Gathering",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "preparing": {
      "label": "Preparing",
      "variant": "state",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "subbar_1040_1041": "Draft",
        "subbar_entity_returns": "Working"
      }
    },
    "prepared": {
      "label": "Prepared",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "in_review": {
      "label": "In review",
      "variant": "state",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "subbar_rail_rows": "In review · {level}"
      }
    },
    "action_required": {
      "label": "Action required",
      "variant": "red-tint",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "home_and_tax_tiles": "Issues"
      }
    },
    "approved": {
      "label": "Approved",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "awaiting_signature": {
      "label": "Awaiting signature",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "filed": {
      "label": "Filed",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "accepted": {
      "label": "Accepted",
      "variant": "green",
      "terminal": true,
      "derived": false
    },
    "rejected": {
      "label": "Rejected",
      "variant": "red-tint",
      "terminal": false,
      "derived": false
    },
    "fixing": {
      "label": "Fixing",
      "variant": "state",
      "terminal": false,
      "derived": false
    }
  },
  "return_flag": {
    "extended": {
      "label": "Extended",
      "variant": "tag",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "tag": "Extended · {date}"
      }
    },
    "on_hold": {
      "label": "On hold",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "superseded": {
      "label": "Superseded",
      "variant": "soon",
      "terminal": true,
      "derived": false
    },
    "amended": {
      "label": "Amended",
      "variant": "tag",
      "terminal": false,
      "derived": false
    }
  },
  "return_sync_chip": {
    "not_yet_exported": {
      "label": "Not yet exported",
      "variant": "outline",
      "terminal": false,
      "derived": false,
      "disc": "refresh_amber"
    },
    "ready_for_export": {
      "label": "Ready for export",
      "variant": "outline",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "tile": "Ready"
      },
      "disc": "refresh_amber"
    },
    "exporting": {
      "label": "Exporting…",
      "variant": "outline",
      "terminal": false,
      "derived": false,
      "disc": "spinner"
    },
    "synced": {
      "label": "Synced {date}",
      "variant": "outline",
      "terminal": false,
      "derived": false,
      "disc": "check_olive"
    },
    "out_of_sync": {
      "label": "Out of sync",
      "variant": "outline",
      "terminal": false,
      "derived": false,
      "disc": "triangle_amber"
    },
    "import_pending_approval": {
      "label": "Import pending approval",
      "variant": "outline",
      "terminal": false,
      "derived": false,
      "disc": "dot_amber"
    },
    "failed": {
      "label": "Export failed",
      "variant": "outline",
      "terminal": false,
      "derived": false,
      "disc": "x_brick"
    }
  },
  "k1_package": {
    "not_prepared": {
      "label": "Not prepared",
      "variant": "neutral",
      "terminal": false,
      "derived": false,
      "clientLabel": "Not released yet"
    },
    "draft": {
      "label": "Draft K-1 · pre-release",
      "variant": "amber",
      "terminal": false,
      "derived": false,
      "clientLabel": "Not released yet"
    },
    "released": {
      "label": "Released {date}",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "viewed": {
      "label": "Viewed",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "downloaded": {
      "label": "Downloaded",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "bounced": {
      "label": "Bounced",
      "variant": "red-tint",
      "terminal": false,
      "derived": false
    },
    "superseded": {
      "label": "Superseded (amended K-1)",
      "variant": "soon",
      "terminal": true,
      "derived": false
    }
  },
  "audit_engagement": {
    "planning": {
      "label": "Planning",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "fieldwork": {
      "label": "Fieldwork",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "in_review": {
      "label": "In review",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "completion": {
      "label": "Completion",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "ready_to_release": {
      "label": "Ready to release",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "released": {
      "label": "Released {date}",
      "variant": "green",
      "terminal": false,
      "derived": false
    },
    "archiving": {
      "label": "Archive in {days} days",
      "variant": "muted",
      "terminal": false,
      "derived": false,
      "disc": "clock"
    },
    "archived": {
      "label": "Archived",
      "variant": "soon",
      "terminal": true,
      "derived": false,
      "disc": "lock"
    },
    "processing": {
      "label": "Processing",
      "variant": "state",
      "terminal": false,
      "derived": true
    }
  },
  "audit_section": {
    "not_started": {
      "label": "Not started",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring"
    },
    "queued": {
      "label": "Queued",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring"
    },
    "waiting_on_inputs": {
      "label": "Waiting on inputs",
      "variant": null,
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "pill_when_idle": "In progress",
        "sub_line_when_run_active": "Waiting on inputs"
      },
      "disc": "half"
    },
    "ready_to_run": {
      "label": "Ready",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring"
    },
    "in_progress": {
      "label": "In progress",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "half"
    },
    "running": {
      "label": "Running",
      "variant": null,
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "pill": "In progress"
      },
      "disc": "spinner"
    },
    "blocked_on_decision": {
      "label": "Blocked on a {role} decision",
      "variant": null,
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "pill": "In progress"
      },
      "disc": "triangle_amber"
    },
    "draft_ready": {
      "label": "Ready",
      "variant": null,
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "sub_line": "Complete · {time}"
      },
      "disc": "check_olive"
    },
    "prepared": {
      "label": "Prepared · {initials}",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "check_grey"
    },
    "reviewed": {
      "label": "Reviewed · {initials}",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "check_olive"
    },
    "signed_off": {
      "label": "Signed off",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "check_olive"
    },
    "locked": {
      "label": "Locked",
      "variant": "soon",
      "terminal": true,
      "derived": false,
      "disc": "lock"
    },
    "failed": {
      "label": "Failed — see run",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "x_brick"
    },
    "changed_after_signoff": {
      "label": "Changed after sign-off",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "triangle_amber"
    }
  },
  "program_board": {
    "not_started": {
      "label": "Not started",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring"
    },
    "in_progress": {
      "label": "In progress",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "half"
    },
    "in_review": {
      "label": "In review",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "dot_amber"
    },
    "complete": {
      "label": "Complete",
      "variant": null,
      "terminal": true,
      "derived": false,
      "disc": "check_olive"
    }
  },
  "control_board": {
    "not_started": {
      "label": "Not started",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring"
    },
    "testing": {
      "label": "Testing",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "spinner"
    },
    "pending": {
      "label": "Pending",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "preparer_review": {
      "label": "Preparer review",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "half"
    },
    "manager_review": {
      "label": "Manager review",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "half"
    },
    "review_complete": {
      "label": "Review complete",
      "variant": null,
      "terminal": true,
      "derived": false,
      "disc": "check_olive"
    }
  },
  "card_overlay": {
    "needs_input": {
      "label": "Needs input",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "waiting_on_client": {
      "label": "Waiting on client",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "agent_running": {
      "label": "Agent running",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "spinner"
    },
    "sent_back": {
      "label": "Sent back",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "left_bar_brick"
    }
  },
  "control_test_result": {
    "not_tested": {
      "label": "Not tested",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring"
    },
    "no_exceptions_noted": {
      "label": "No exceptions noted",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "check_olive"
    },
    "exceptions_noted": {
      "label": "Exceptions noted",
      "variant": "red-tint",
      "terminal": false,
      "derived": false
    },
    "not_applicable": {
      "label": "Not applicable",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "attest_exception": {
    "noted": {
      "label": "Noted",
      "variant": "red-tint",
      "terminal": false,
      "derived": false
    },
    "response_received": {
      "label": "Response received",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "evaluated": {
      "label": "Evaluated",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    }
  },
  "deficiency": {
    "exception_for_resolution": {
      "label": "Exception for resolution",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "proposed": {
      "label": "Proposed",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "concluded": {
      "label": "Concluded",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "communicated": {
      "label": "Communicated",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    }
  },
  "deficiency_severity": {
    "deficiency": {
      "label": "Deficiency",
      "variant": "red-tint",
      "terminal": false,
      "derived": false
    },
    "significant_deficiency": {
      "label": "Significant deficiency",
      "variant": "red",
      "terminal": false,
      "derived": false
    },
    "material_weakness": {
      "label": "Material weakness",
      "variant": "red",
      "terminal": false,
      "derived": false
    }
  },
  "misstatement": {
    "candidate": {
      "label": "Candidate",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "confirmed": {
      "label": "Confirmed",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "below_ct": {
      "label": "Below CT",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "proposed_to_client": {
      "label": "Proposed to client",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "booked": {
      "label": "Booked",
      "variant": "green",
      "terminal": true,
      "derived": false
    },
    "passed_on_sum": {
      "label": "Passed on SUM",
      "variant": "neutral",
      "terminal": true,
      "derived": false
    }
  },
  "misstatement_type": {
    "factual": {
      "label": "Factual",
      "variant": "tag",
      "terminal": false,
      "derived": false
    },
    "judgmental": {
      "label": "Judgmental",
      "variant": "tag",
      "terminal": false,
      "derived": false
    },
    "projected": {
      "label": "Projected",
      "variant": "tag",
      "terminal": false,
      "derived": false
    }
  },
  "ia_issue_rating": {
    "high": {
      "label": "High",
      "variant": "red",
      "terminal": false,
      "derived": false
    },
    "medium": {
      "label": "Medium",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "low": {
      "label": "Low",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    }
  },
  "action_plan": {
    "open": {
      "label": "Open",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "in_progress": {
      "label": "In progress",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "implemented": {
      "label": "Implemented",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "validated": {
      "label": "Validated",
      "variant": "green",
      "terminal": true,
      "derived": false
    },
    "overdue": {
      "label": "Overdue",
      "variant": "red-tint",
      "terminal": false,
      "derived": true
    }
  },
  "close": {
    "not_started": {
      "label": "Not started",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "in_progress": {
      "label": "In progress",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "in_review": {
      "label": "In review",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "approved": {
      "label": "Approved",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "delivered": {
      "label": "Delivered",
      "variant": "green",
      "terminal": false,
      "derived": false
    },
    "locked": {
      "label": "Locked",
      "variant": "soon",
      "terminal": true,
      "derived": false
    },
    "past_due": {
      "label": "{n} days past due",
      "variant": null,
      "terminal": false,
      "derived": true
    }
  },
  "close_task": {
    "queued": {
      "label": "Queued",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring"
    },
    "running": {
      "label": "Running",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "spinner"
    },
    "needs_attention": {
      "label": "Needs attention",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "triangle_amber"
    },
    "done": {
      "label": "Done",
      "variant": null,
      "terminal": true,
      "derived": false,
      "disc": "check_olive"
    },
    "failed": {
      "label": "Failed",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "x_brick"
    }
  },
  "proposed_entry": {
    "proposed": {
      "label": "Proposed",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "within_threshold": {
      "label": "Within threshold",
      "variant": null,
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "with_class": "Within threshold · ≤ {amount} {class}"
      },
      "disc": "check_olive"
    },
    "review_required": {
      "label": "Review required",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring"
    },
    "approved": {
      "label": "Approved",
      "variant": "green",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "attribution": "Approved by {person} under {policy}"
      }
    },
    "client_approved": {
      "label": "Client approved",
      "variant": "green",
      "terminal": false,
      "derived": false
    },
    "posted": {
      "label": "Posted",
      "variant": "green-tint",
      "terminal": true,
      "derived": false,
      "contextLabels": {
        "with_ref": "Posted · {system} {ref}"
      }
    },
    "failed_post": {
      "label": "Failed post",
      "variant": "red",
      "terminal": false,
      "derived": false
    },
    "reversed": {
      "label": "Reversed",
      "variant": "soon",
      "terminal": true,
      "derived": false
    }
  },
  "tie_out_tally": {
    "tie": {
      "label": "tie",
      "variant": "green",
      "terminal": false,
      "derived": false
    },
    "off": {
      "label": "off {amount}",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "check": {
      "label": "Check",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "pending": {
      "label": "Pending",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "ties_once_posted": {
      "label": "Ties once posted",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "conic_dot_amber"
    },
    "reconciled": {
      "label": "Reconciled",
      "variant": "green",
      "terminal": true,
      "derived": false
    }
  },
  "request": {
    "draft": {
      "label": "Draft",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "requested": {
      "label": "Requested {date}",
      "variant": null,
      "terminal": false,
      "derived": false,
      "clientLabel": "To do",
      "disc": "ring"
    },
    "uploaded": {
      "label": "Uploaded – needs review",
      "variant": null,
      "terminal": false,
      "derived": false,
      "clientLabel": "Done",
      "disc": "dot_amber"
    },
    "received": {
      "label": "Received ✓",
      "variant": "green",
      "terminal": true,
      "derived": false,
      "clientLabel": "Done"
    },
    "returned": {
      "label": "Returned · {reason}",
      "variant": "red-tint",
      "terminal": false,
      "derived": false,
      "clientLabel": "Returned"
    },
    "not_applicable": {
      "label": "Not applicable",
      "variant": "muted",
      "terminal": true,
      "derived": false,
      "clientLabel": "Ignored"
    },
    "overdue": {
      "label": "Overdue",
      "variant": "red-tint",
      "terminal": false,
      "derived": true
    }
  },
  "request_close": {
    "requested": {
      "label": "Requested",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring"
    },
    "received": {
      "label": "Received",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "dot_amber"
    },
    "matched": {
      "label": "Matched",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "pending_incorporation": {
      "label": "Pending incorporation",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "incorporated": {
      "label": "Incorporated",
      "variant": "green",
      "terminal": true,
      "derived": false
    }
  },
  "document": {
    "uploading": {
      "label": "Uploading",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring_upload"
    },
    "processing": {
      "label": "Processing",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "spinner"
    },
    "classified": {
      "label": "Classified",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "matched": {
      "label": "Matched",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "approved": {
      "label": "Approved",
      "variant": null,
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "row_micro_pill": "✓ {n}"
      },
      "disc": "check_ink_micro"
    },
    "rejected": {
      "label": "Rejected",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "x_grey"
    },
    "superseded": {
      "label": "Superseded",
      "variant": "soon",
      "terminal": true,
      "derived": false
    }
  },
  "evidence_screening": {
    "passed": {
      "label": "Passed",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "check_olive"
    },
    "flagged": {
      "label": "Flagged",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "triangle_amber"
    },
    "not_screened": {
      "label": "Not screened",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring"
    }
  },
  "inbox_item": {
    "new": {
      "label": "New",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring_16"
    },
    "waiting": {
      "label": "Waiting",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "dot_gold_16"
    },
    "filed": {
      "label": "Filed",
      "variant": null,
      "terminal": true,
      "derived": false,
      "disc": "check_olive_15"
    },
    "ignored": {
      "label": "Ignored",
      "variant": null,
      "terminal": true,
      "derived": false,
      "disc": "x_ink4_15"
    }
  },
  "issue": {
    "open": {
      "label": "Open",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "flag"
    },
    "in_progress": {
      "label": "In progress",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "atom_spinner"
    },
    "resolved": {
      "label": "Resolved",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "check_olive"
    },
    "verified": {
      "label": "Verified",
      "variant": null,
      "terminal": true,
      "derived": false,
      "disc": "check_olive"
    },
    "reopened": {
      "label": "Reopened",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "flag"
    },
    "not_applicable": {
      "label": "Not applicable",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "issue_severity": {
    "high": {
      "label": "High",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "flag_brick"
    },
    "medium": {
      "label": "Medium",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "flag_amber"
    },
    "low": {
      "label": "Low",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "flag_amber"
    }
  },
  "issue_audit_route": {
    "under_evaluation": {
      "label": "Under evaluation",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "converted_to_misstatement": {
      "label": "Converted to misstatement",
      "variant": "neutral",
      "terminal": true,
      "derived": false
    },
    "converted_to_deficiency": {
      "label": "Converted to deficiency",
      "variant": "neutral",
      "terminal": true,
      "derived": false
    }
  },
  "review_note": {
    "open": {
      "label": "Open",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "responded": {
      "label": "Responded",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "cleared": {
      "label": "Cleared",
      "variant": "green",
      "terminal": false,
      "derived": false
    },
    "closed": {
      "label": "Closed",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    },
    "withdrawn": {
      "label": "Withdrawn",
      "variant": "soon",
      "terminal": true,
      "derived": false
    }
  },
  "comment_thread": {
    "open": {
      "label": "Open",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "resolved": {
      "label": "Resolved",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "todo": {
    "open": {
      "label": "Open",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "ring"
    },
    "done": {
      "label": "Done",
      "variant": null,
      "terminal": true,
      "derived": false,
      "disc": "check_olive"
    },
    "overdue": {
      "label": "Overdue",
      "variant": "red-tint",
      "terminal": false,
      "derived": true
    }
  },
  "envelope": {
    "draft": {
      "label": "Draft",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "sent": {
      "label": "Sent",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "viewed": {
      "label": "Viewed",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "partially_signed": {
      "label": "{signed} of {total} signed",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "completed": {
      "label": "Completed",
      "variant": "green",
      "terminal": true,
      "derived": false
    },
    "declined": {
      "label": "Declined",
      "variant": "red-tint",
      "terminal": true,
      "derived": false
    },
    "expired": {
      "label": "Expired",
      "variant": "muted",
      "terminal": true,
      "derived": false
    },
    "voided": {
      "label": "Voided",
      "variant": "soon",
      "terminal": true,
      "derived": false
    }
  },
  "notice": {
    "received": {
      "label": "New",
      "variant": "red-tint",
      "terminal": false,
      "derived": false
    },
    "classified": {
      "label": "Classified",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "analyzing": {
      "label": "Analyzing",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "response_drafted": {
      "label": "Response drafted",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "approved": {
      "label": "Approved",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "sent": {
      "label": "Response sent",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "awaiting_irs": {
      "label": "Awaiting IRS",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "closed": {
      "label": "Resolved",
      "variant": "green",
      "terminal": true,
      "derived": false
    },
    "escalated": {
      "label": "Escalated",
      "variant": "red-tint",
      "terminal": false,
      "derived": false
    }
  },
  "consent": {
    "requested": {
      "label": "Requested",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "signed": {
      "label": "Signed · expires {date}",
      "variant": "green",
      "terminal": false,
      "derived": false
    },
    "expiring": {
      "label": "Expiring",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "expired": {
      "label": "Expired",
      "variant": "red-tint",
      "terminal": true,
      "derived": false
    },
    "declined": {
      "label": "Declined",
      "variant": "neutral",
      "terminal": true,
      "derived": false
    },
    "revoked": {
      "label": "Revoked",
      "variant": "soon",
      "terminal": true,
      "derived": false
    }
  },
  "consent_purpose": {
    "use": {
      "label": "Consent to use",
      "variant": "tag",
      "terminal": false,
      "derived": false
    },
    "ai_disclosure": {
      "label": "Consent to disclose — AI sub-processors",
      "variant": "tag",
      "terminal": false,
      "derived": false
    },
    "offshore_disclosure": {
      "label": "Consent to disclose — offshore preparers",
      "variant": "tag",
      "terminal": false,
      "derived": false
    },
    "third_party_disclosure": {
      "label": "Consent to disclose — named third party",
      "variant": "tag",
      "terminal": false,
      "derived": false
    }
  },
  "agent_run": {
    "queued": {
      "label": "Queued",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "planning": {
      "label": "Planning…",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "spinner"
    },
    "awaiting_plan_approval": {
      "label": "Plan ready — approve?",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "dispatched": {
      "label": "Dispatched",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "running": {
      "label": "Running",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "spinner"
    },
    "needs_input": {
      "label": "Needs your answer",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "blocked_on_decision": {
      "label": "Blocked on a {role} decision",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "triangle_amber"
    },
    "waiting_on_inputs": {
      "label": "Waiting on inputs",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "succeeded": {
      "label": "Ready for review",
      "variant": "state",
      "terminal": true,
      "derived": false
    },
    "approved": {
      "label": "Approved",
      "variant": "green",
      "terminal": true,
      "derived": true
    },
    "partially_approved": {
      "label": "{n} of {total} approved",
      "variant": "green-tint",
      "terminal": true,
      "derived": true
    },
    "rejected": {
      "label": "Rejected",
      "variant": "red-tint",
      "terminal": true,
      "derived": true
    },
    "failed": {
      "label": "Failed",
      "variant": "red",
      "terminal": true,
      "derived": false,
      "contextLabels": {
        "run_row": "Failed — see run"
      }
    },
    "cancelled": {
      "label": "Cancelled",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "workbench_session": {
    "live": {
      "label": "Live",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "dot_olive"
    },
    "running": {
      "label": "Running",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "spinner"
    },
    "awaiting_answer": {
      "label": "Needs your answer",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "dot_amber"
    },
    "ready_for_review": {
      "label": "Ready for review",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "complete": {
      "label": "Complete",
      "variant": null,
      "terminal": true,
      "derived": false,
      "disc": "check_olive"
    },
    "failed": {
      "label": "Failed",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "x_brick"
    }
  },
  "integration": {
    "available": {
      "label": "Available",
      "variant": "outline",
      "terminal": false,
      "derived": false
    },
    "connecting": {
      "label": "Connecting",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "spinner"
    },
    "connected": {
      "label": "Connected",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "check_olive"
    },
    "needs_attention": {
      "label": "Needs attention",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "needs_reauth": {
      "label": "Needs reauth",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "disconnected": {
      "label": "Disconnected",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "coming_soon": {
      "label": "Coming soon",
      "variant": "soon",
      "terminal": false,
      "derived": false
    },
    "paused": {
      "label": "Paused",
      "variant": "muted",
      "terminal": false,
      "derived": false
    }
  },
  "agent_template": {
    "available": {
      "label": "Available",
      "variant": "outline",
      "terminal": false,
      "derived": false
    },
    "installed": {
      "label": "Installed",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "check_olive"
    },
    "update_available": {
      "label": "Update available",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "coming_soon": {
      "label": "Coming soon",
      "variant": "soon",
      "terminal": false,
      "derived": false
    }
  },
  "template_version": {
    "draft": {
      "label": "Draft",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "published": {
      "label": "Published",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "deprecated": {
      "label": "Deprecated",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "engagement_template_link": {
    "current": {
      "label": "Current",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "update_available": {
      "label": "Update available",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "updated": {
      "label": "Updated {date}",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "held": {
      "label": "Held",
      "variant": "muted",
      "terminal": false,
      "derived": false
    }
  },
  "trigger": {
    "on": {
      "label": "On",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "off": {
      "label": "Off",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "duplicate": {
      "label": "Duplicate",
      "variant": "amber",
      "terminal": false,
      "derived": false
    }
  },
  "saved_prompt_access": {
    "firm": {
      "label": "Firm",
      "variant": "tag",
      "terminal": false,
      "derived": false
    },
    "service_line": {
      "label": "Service line",
      "variant": "tag",
      "terminal": false,
      "derived": false
    },
    "personal": {
      "label": "Personal",
      "variant": "tag",
      "terminal": false,
      "derived": false
    }
  },
  "learned_context_item": {
    "proposed": {
      "label": "Proposed",
      "variant": "outline",
      "terminal": false,
      "derived": false
    },
    "approved": {
      "label": "Approved",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "retired": {
      "label": "Retired",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "binder": {
    "draft": {
      "label": "Draft",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "published": {
      "label": "Published",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "unpublished": {
      "label": "Unpublished",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "complete": {
      "label": "Complete",
      "variant": "green-tint",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "mark_as_done": "Marked done by {person}"
      }
    },
    "closed": {
      "label": "Closed",
      "variant": "soon",
      "terminal": true,
      "derived": false
    }
  },
  "archive": {
    "assembling": {
      "label": "Archive in {days} days",
      "variant": "muted",
      "terminal": false,
      "derived": false,
      "disc": "clock"
    },
    "locked": {
      "label": "Locked · WORM",
      "variant": "soon",
      "terminal": false,
      "derived": false,
      "disc": "lock"
    },
    "post_lock_addition": {
      "label": "Addition logged",
      "variant": "amber",
      "terminal": false,
      "derived": false
    }
  },
  "checkpoint": {
    "proposed": {
      "label": "Proposed",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "approved": {
      "label": "Approved",
      "variant": "green",
      "terminal": false,
      "derived": false
    },
    "rejected": {
      "label": "Rejected",
      "variant": "red-tint",
      "terminal": true,
      "derived": false
    },
    "current": {
      "label": "Current",
      "variant": "tag",
      "terminal": false,
      "derived": false
    }
  },
  "project": {
    "scoping": {
      "label": "Scoping",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "active": {
      "label": "Active",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "delivered": {
      "label": "Delivered",
      "variant": "green",
      "terminal": false,
      "derived": false
    },
    "closed": {
      "label": "Closed",
      "variant": "soon",
      "terminal": true,
      "derived": false
    }
  },
  "consolidation": {
    "draft": {
      "label": "Draft",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "finalized": {
      "label": "Finalized",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    }
  },
  "elimination_entry": {
    "proposed": {
      "label": "Proposed",
      "variant": "outline",
      "terminal": false,
      "derived": false
    },
    "approved": {
      "label": "Approved",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "posted": {
      "label": "Posted",
      "variant": "green",
      "terminal": true,
      "derived": false
    }
  },
  "component": {
    "full_scope": {
      "label": "Full scope",
      "variant": "tag",
      "terminal": false,
      "derived": false
    },
    "specific_procedures": {
      "label": "Specific procedures",
      "variant": "tag",
      "terminal": false,
      "derived": false
    },
    "analytical_only": {
      "label": "Analytical only",
      "variant": "tag",
      "terminal": false,
      "derived": false
    }
  },
  "component_instructions": {
    "draft": {
      "label": "Draft",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "sent": {
      "label": "Sent",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "acknowledged": {
      "label": "Acknowledged",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    }
  },
  "component_deliverable": {
    "expected": {
      "label": "Expected",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "received": {
      "label": "Received",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "reviewed": {
      "label": "Reviewed",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    },
    "late": {
      "label": "Late",
      "variant": "red-tint",
      "terminal": false,
      "derived": true
    }
  },
  "linked_value": {
    "tb_linked": {
      "label": "TB-linked",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "formula": {
      "label": "Formula",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "override": {
      "label": "Override",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "dotted_underline_amber"
    },
    "stale_override": {
      "label": "Stale override",
      "variant": null,
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "action": "↺ Relink"
      },
      "disc": "amber_tint_relink"
    }
  }
} as const;
