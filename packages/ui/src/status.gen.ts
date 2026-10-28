// GENERATED from docs/product/status-vocabulary.yaml. Do not edit.
// Regenerate: python -m abacus_tools.codegen.status_vocabulary (C2; F-03-T09, F-05-T12).

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
      "derived": false,
      "contextVariants": {
        "subbar": "state"
      }
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
  "engagement_export": {
    "queued": {
      "label": "Queued",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "packaging": {
      "label": "Packaging…",
      "variant": "state",
      "terminal": false,
      "derived": false,
      "disc": "spinner"
    },
    "ready": {
      "label": "Ready",
      "variant": "green-tint",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "sheet": "Download · {n} files · {size} · expires {date}"
      }
    },
    "failed": {
      "label": "Export failed",
      "variant": "red-tint",
      "terminal": true,
      "derived": false,
      "disc": "x_brick"
    },
    "expired": {
      "label": "Expired",
      "variant": "soon",
      "terminal": true,
      "derived": false
    },
    "undone": {
      "label": "Undone",
      "variant": "muted",
      "terminal": true,
      "derived": false
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
      "derived": false,
      "emphasis": "bold"
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
      "disc": "ring",
      "textTone": "amber"
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
      "disc": "conic_dot_amber",
      "textTone": "amber"
    },
    "reconciled": {
      "label": "Reconciled",
      "variant": "green",
      "terminal": true,
      "derived": false
    }
  },
  "trial_balance_label": {
    "standard": {
      "label": "Standard",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "interim": {
      "label": "Interim",
      "variant": null,
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "chip": "TB: Interim · {date}"
      }
    },
    "prior": {
      "label": "Prior",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "budget": {
      "label": "Budget",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "preliminary": {
      "label": "Preliminary",
      "variant": null,
      "terminal": false,
      "derived": false
    }
  },
  "trial_balance_layer": {
    "unadjusted": {
      "label": "Unadjusted",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "aje": {
      "label": "AJE",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "rje": {
      "label": "RJE",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "final": {
      "label": "Final",
      "variant": null,
      "terminal": false,
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
    },
    "held": {
      "label": "Waiting",
      "variant": null,
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "sub_line": "Asked the client · {date}"
      },
      "disc": "dot_gold_16"
    },
    "withdrawn": {
      "label": "Withdrawn",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "inbox_thread": {
    "unmatched": {
      "label": "Unmatched",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "matched": {
      "label": "Matched",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "ignored": {
      "label": "Ignored",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "portal_intake_upload": {
    "sent": {
      "label": "Sent",
      "variant": null,
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "to_firm": "Sent to {firm}"
      }
    },
    "received": {
      "label": "Received by {firm}",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    },
    "withdrawn": {
      "label": "Withdrawn",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "file_document": {
    "processing": {
      "label": "Processing",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "needs_review": {
      "label": "Uploaded – needs review",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "accepted": {
      "label": "Approved",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "check_olive"
    },
    "superseded": {
      "label": "Superseded",
      "variant": "muted",
      "terminal": true,
      "derived": false,
      "contextLabels": {
        "replaced_by": "Superseded · replaced by {name} · {date}"
      }
    },
    "on_hold": {
      "label": "On hold",
      "variant": "amber",
      "terminal": false,
      "derived": false
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
  "sign_off_slot": {
    "signed": {
      "label": "✓ {initials}",
      "variant": "green-tint",
      "terminal": false,
      "derived": true,
      "contextLabels": {
        "with_date": "✓ {initials} · {date}"
      }
    },
    "stale": {
      "label": "Changed after sign-off",
      "variant": "amber",
      "terminal": false,
      "derived": true,
      "contextLabels": {
        "struck_chip": "✓ {initials} · {date} (before this change)"
      }
    }
  },
  "human_gate": {
    "open": {
      "label": "Open",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "done": {
      "label": "Done",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    },
    "voided": {
      "label": "Voided",
      "variant": "muted",
      "terminal": true,
      "derived": false
    },
    "snoozed": {
      "label": "Snoozed until {date}",
      "variant": "neutral",
      "terminal": false,
      "derived": true
    }
  },
  "due_risk": {
    "overdue": {
      "label": "Overdue",
      "variant": "red-tint",
      "terminal": false,
      "derived": true
    },
    "due_soon": {
      "label": "{date} · {n} days",
      "variant": "red-tint",
      "terminal": false,
      "derived": true
    },
    "approaching": {
      "label": "{date} · {n} days",
      "variant": "state",
      "terminal": false,
      "derived": true
    },
    "later": {
      "label": "{date}",
      "variant": "neutral",
      "terminal": false,
      "derived": true
    }
  },
  "decision_card": {
    "awaiting_role": {
      "label": "Waiting on {person}",
      "variant": null,
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "banner": "Waiting on {person} · requested {time}",
        "history": "Proposed"
      },
      "contextVariants": {
        "history": "state"
      }
    },
    "decided": {
      "label": "Decided",
      "variant": "green",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "history_reassessed": "No change"
      },
      "contextVariants": {
        "history": "green-tint",
        "history_reassessed": "neutral"
      }
    },
    "superseded": {
      "label": "Superseded by v{n}",
      "variant": "soon",
      "terminal": true,
      "derived": false
    }
  },
  "field_value": {
    "updated": {
      "label": "Updated",
      "variant": "amber",
      "terminal": false,
      "derived": true
    },
    "edited": {
      "label": "Edited",
      "variant": "amber",
      "terminal": false,
      "derived": true
    },
    "estimate": {
      "label": "≈",
      "variant": null,
      "terminal": false,
      "derived": true,
      "disc": "estimate_badge"
    },
    "unsupported": {
      "label": "Unsupported",
      "variant": "red-tint",
      "terminal": false,
      "derived": true
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
  "methodology_version": {
    "draft": {
      "label": "Draft",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "parsing": {
      "label": "Parsing…",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "needs_review": {
      "label": "Needs review",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "published": {
      "label": "Published",
      "variant": "green-tint",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "knw02": "Approved"
      }
    },
    "superseded": {
      "label": "Superseded",
      "variant": "soon",
      "terminal": true,
      "derived": false
    },
    "discarded": {
      "label": "Discarded",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "methodology_import": {
    "awaiting_files": {
      "label": "Awaiting files",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "scanning": {
      "label": "Scanning",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "parsing": {
      "label": "Parsing…",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "needs_review": {
      "label": "Needs review",
      "variant": "state",
      "terminal": true,
      "derived": false
    },
    "failed": {
      "label": "Failed",
      "variant": "red-tint",
      "terminal": true,
      "derived": false
    },
    "cancelled": {
      "label": "Cancelled",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "knowledge_item": {
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
    "superseded": {
      "label": "Superseded",
      "variant": "soon",
      "terminal": true,
      "derived": false
    }
  },
  "parse_flag": {
    "low_confidence": {
      "label": "Low confidence",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "split_across_pages": {
      "label": "Split across pages",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "numbering_gap": {
      "label": "Numbering gap",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "unverified_citation": {
      "label": "Unverified citation",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "cross_reference_missing": {
      "label": "Cross-reference missing",
      "variant": "amber",
      "terminal": false,
      "derived": false
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
  "envelope_signer": {
    "pending": {
      "label": "Waiting",
      "variant": "neutral",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "chip": "○ {name}"
      }
    },
    "viewed": {
      "label": "Viewed",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "verified": {
      "label": "Identity verified",
      "variant": "neutral",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "signer_band": "Identity verified {time} · {n} fields left"
      }
    },
    "signed": {
      "label": "Signed",
      "variant": "green-tint",
      "terminal": true,
      "derived": false,
      "contextLabels": {
        "with_date": "Signed · {date}",
        "chip": "✓ {name} · {date}",
        "signer_band": "✓ Signed {date}, {time} · identity verified"
      }
    },
    "declined": {
      "label": "Declined",
      "variant": "red-tint",
      "terminal": true,
      "derived": false
    },
    "verification_failed": {
      "label": "Needs a handwritten signature",
      "variant": "amber",
      "terminal": false,
      "derived": false
    }
  },
  "signing_step": {
    "verify": {
      "label": "Verify identity",
      "variant": null,
      "terminal": false,
      "derived": true,
      "contextLabels": {
        "chip": "Verify"
      }
    },
    "review": {
      "label": "Review",
      "variant": null,
      "terminal": false,
      "derived": true
    },
    "sign": {
      "label": "Sign",
      "variant": null,
      "terminal": false,
      "derived": true
    },
    "done": {
      "label": "Done",
      "variant": null,
      "terminal": true,
      "derived": true
    }
  },
  "envelope_purpose": {
    "e_file_authorization": {
      "label": "E-file authorization",
      "variant": "tag",
      "terminal": false,
      "derived": false
    },
    "engagement_letter": {
      "label": "Engagement letter",
      "variant": "tag",
      "terminal": false,
      "derived": false
    },
    "representation_letter": {
      "label": "Rep letter",
      "variant": "tag",
      "terminal": false,
      "derived": false
    },
    "consent_7216": {
      "label": "§7216 consent",
      "variant": "tag",
      "terminal": false,
      "derived": false
    }
  },
  "generated_document": {
    "drafting": {
      "label": "Drafting",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "draft": {
      "label": "Draft",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "approved": {
      "label": "Approved",
      "variant": "green-tint",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "meta_line": "Approved by {actor} · {when}"
      }
    },
    "locked": {
      "label": "Locked",
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
  "suggestion": {
    "pending": {
      "label": "Suggestion",
      "variant": null,
      "terminal": false,
      "derived": false,
      "disc": "atom"
    },
    "adopted": {
      "label": "Adopted by {initials}",
      "variant": null,
      "terminal": true,
      "derived": false,
      "disc": "atom_olive"
    },
    "edited": {
      "label": "Edited by {initials}",
      "variant": null,
      "terminal": true,
      "derived": false,
      "contextLabels": {
        "with_prior": "Edited by {initials} · was {value}"
      },
      "disc": "atom_olive"
    },
    "dismissed": {
      "label": "Dismissed",
      "variant": null,
      "terminal": true,
      "derived": false
    },
    "superseded": {
      "label": "Superseded",
      "variant": "soon",
      "terminal": true,
      "derived": false
    },
    "expired": {
      "label": "Expired",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "proposal": {
    "pending": {
      "label": "Ready for review",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "approved": {
      "label": "Approved",
      "variant": "green",
      "terminal": true,
      "derived": false,
      "contextLabels": {
        "attribution": "Approved by {person}",
        "under_policy": "✓ Approved by {person} under {policy} · {time}"
      }
    },
    "approved_with_edits": {
      "label": "Approved with edits",
      "variant": "green",
      "terminal": true,
      "derived": false
    },
    "rejected": {
      "label": "Rejected",
      "variant": "red-tint",
      "terminal": true,
      "derived": false,
      "contextLabels": {
        "attribution": "Rejected by {person} · reason: {reason}"
      }
    },
    "superseded": {
      "label": "Superseded",
      "variant": "soon",
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
      "derived": false,
      "clientLabel": "Not connected"
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
      "derived": false,
      "contextLabels": {
        "attribution": "Approved · {person} · {time}"
      }
    },
    "rejected": {
      "label": "Rejected",
      "variant": "red-tint",
      "terminal": true,
      "derived": false,
      "contextLabels": {
        "attribution": "{person} · reason: {reason}"
      }
    },
    "saved": {
      "label": "Saved",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "current": {
      "label": "Current",
      "variant": "tag",
      "terminal": false,
      "derived": true
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
  },
  "client": {
    "prospect": {
      "label": "Prospect",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "active": {
      "label": "Active",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "inactive": {
      "label": "Inactive",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "former": {
      "label": "Former",
      "variant": null,
      "terminal": true,
      "derived": false
    }
  },
  "invitation": {
    "not_invited": {
      "label": "Not invited",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "invited": {
      "label": "Invite pending · expires {date}",
      "variant": "amber",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "portal_pill": "Invited"
      }
    },
    "active": {
      "label": "Active",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "locked": {
      "label": "Locked",
      "variant": "red-tint",
      "terminal": false,
      "derived": false
    },
    "deactivated": {
      "label": "Deactivated {date}",
      "variant": "tag",
      "terminal": true,
      "derived": false
    }
  },
  "acceptance_record": {
    "draft": {
      "label": "Draft",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "pre_screening": {
      "label": "Pre-screening",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "awaiting_partner": {
      "label": "Awaiting partner",
      "variant": "amber",
      "terminal": false,
      "derived": false,
      "contextLabels": {
        "rail_card": "Blocked on a partner decision"
      }
    },
    "decided": {
      "label": "Decided",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    },
    "declined": {
      "label": "Declined",
      "variant": null,
      "terminal": true,
      "derived": false
    }
  },
  "letter": {
    "not_started": {
      "label": "Not started",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "draft": {
      "label": "Draft",
      "variant": "neutral",
      "terminal": false,
      "derived": false
    },
    "partner_approved": {
      "label": "Partner approved",
      "variant": "green-tint",
      "terminal": false,
      "derived": false
    },
    "sent": {
      "label": "Sent",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "signed": {
      "label": "Signed",
      "variant": "green",
      "terminal": true,
      "derived": false
    },
    "not_required": {
      "label": "Not required this year",
      "variant": "muted",
      "terminal": true,
      "derived": false
    },
    "superseded": {
      "label": "Superseded",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "letter_clause": {
    "on": {
      "label": "On",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "off": {
      "label": "Off",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "required": {
      "label": "Required",
      "variant": null,
      "terminal": false,
      "derived": false
    }
  },
  "letter_record": {
    "not_signed": {
      "label": "Not signed",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "signed": {
      "label": "Letter signed",
      "variant": "green-tint",
      "terminal": true,
      "derived": false,
      "contextLabels": {
        "gate_row": "Letter signed by {signers} · {date}"
      }
    }
  },
  "conflict_assessment": {
    "pending": {
      "label": "Pending",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "clear": {
      "label": "Clear",
      "variant": "neutral",
      "terminal": true,
      "derived": false
    },
    "same_family_not_adverse": {
      "label": "Same family · not adverse",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    },
    "not_adverse": {
      "label": "Not adverse",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    },
    "counterparty_review": {
      "label": "Counterparty · {relationship} — review",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "conflict": {
      "label": "Conflict",
      "variant": "red-tint",
      "terminal": true,
      "derived": false
    }
  },
  "nas_evaluation": {
    "pending": {
      "label": "Pending",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "concluded": {
      "label": "Concluded",
      "variant": "green",
      "terminal": true,
      "derived": false
    },
    "not_applicable": {
      "label": "Not applicable",
      "variant": "neutral",
      "terminal": true,
      "derived": false
    }
  },
  "independence_conclusion": {
    "independent": {
      "label": "Independent",
      "variant": null,
      "terminal": true,
      "derived": false
    },
    "independent_with_safeguards": {
      "label": "Independent with safeguards",
      "variant": null,
      "terminal": true,
      "derived": false
    },
    "not_independent": {
      "label": "Not independent",
      "variant": null,
      "terminal": true,
      "derived": false
    }
  },
  "citation": {
    "valid": {
      "label": "Verified",
      "variant": null,
      "terminal": false,
      "derived": true
    },
    "moved": {
      "label": "Source moved",
      "variant": "red-tint",
      "terminal": false,
      "derived": true
    },
    "broken": {
      "label": "Broken",
      "variant": "red",
      "terminal": true,
      "derived": true
    },
    "relinked": {
      "label": "Re-linked",
      "variant": "muted",
      "terminal": true,
      "derived": true
    }
  },
  "viewer": {
    "processing": {
      "label": "Processing…",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "ready": {
      "label": "Ready",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "password_protected": {
      "label": "Password-protected",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "unreadable": {
      "label": "Can't read this file",
      "variant": "red-tint",
      "terminal": true,
      "derived": false
    },
    "not_previewable": {
      "label": "Can't preview",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "evidence_unlock": {
    "ready": {
      "label": "Unlocked",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    },
    "wrong_password": {
      "label": "That password didn't open the file.",
      "variant": "red-tint",
      "terminal": false,
      "derived": false
    }
  },
  "membership": {
    "active": {
      "label": "Active",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "invited": {
      "label": "Invite pending",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "deactivated": {
      "label": "Deactivated",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "annual_independence": {
    "confirmed": {
      "label": "Confirmed",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    },
    "not_yet": {
      "label": "Not yet",
      "variant": "muted",
      "terminal": false,
      "derived": false
    },
    "declined": {
      "label": "Declined",
      "variant": "red-tint",
      "terminal": true,
      "derived": false
    }
  },
  "wall_approval": {
    "awaiting": {
      "label": "Awaiting approval",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "approved": {
      "label": "Approved",
      "variant": null,
      "terminal": true,
      "derived": false
    }
  },
  "legal_hold": {
    "applying": {
      "label": "Applying",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "active": {
      "label": "Active",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "releasing": {
      "label": "Releasing",
      "variant": "state",
      "terminal": false,
      "derived": false
    },
    "released": {
      "label": "Released",
      "variant": "muted",
      "terminal": true,
      "derived": false
    }
  },
  "ai_policy_version": {
    "draft": {
      "label": "Draft",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "awaiting_approval": {
      "label": "Awaiting approval",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "published": {
      "label": "Published",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "declined": {
      "label": "Declined",
      "variant": null,
      "terminal": true,
      "derived": false
    },
    "withdrawn": {
      "label": "Withdrawn",
      "variant": null,
      "terminal": true,
      "derived": false
    },
    "superseded": {
      "label": "Superseded",
      "variant": null,
      "terminal": true,
      "derived": true
    }
  },
  "security_incident": {
    "investigating": {
      "label": "Investigating",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "closed": {
      "label": "Closed",
      "variant": null,
      "terminal": true,
      "derived": false
    }
  },
  "firm_export": {
    "awaiting_approval": {
      "label": "Waiting for approval",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "ready": {
      "label": "Ready",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "downloaded": {
      "label": "Downloaded",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "expired": {
      "label": "Expired",
      "variant": null,
      "terminal": true,
      "derived": false
    }
  },
  "firm_export_schedule": {
    "pending_approval": {
      "label": "Waiting for approval",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "active": {
      "label": "Active",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "paused": {
      "label": "Paused",
      "variant": null,
      "terminal": false,
      "derived": false
    }
  },
  "safeguards_control": {
    "evidenced": {
      "label": "Evidenced",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "open": {
      "label": "Open",
      "variant": null,
      "terminal": false,
      "derived": false
    }
  },
  "support_session": {
    "requested": {
      "label": "Awaiting firm approval",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "active": {
      "label": "Granted until {time}",
      "variant": null,
      "terminal": false,
      "derived": false
    },
    "declined": {
      "label": "Declined",
      "variant": null,
      "terminal": true,
      "derived": false
    },
    "revoked": {
      "label": "Revoked",
      "variant": null,
      "terminal": true,
      "derived": false
    }
  },
  "client_invitation": {
    "pending": {
      "label": "Pending",
      "variant": "amber",
      "terminal": false,
      "derived": false
    },
    "accepted": {
      "label": "Accepted",
      "variant": "green-tint",
      "terminal": true,
      "derived": false
    },
    "revoked": {
      "label": "Revoked",
      "variant": null,
      "terminal": true,
      "derived": false
    },
    "expired": {
      "label": "Expired",
      "variant": null,
      "terminal": true,
      "derived": false
    }
  }
} as const;

// Where each word of the handoff status.js went: a registry code, or retired.
export const HANDOFF_WORDS = {
  "Engagement": {
    "Draft": {
      "retired": true,
      "reason": "no Draft engagement state in 3.3.1; nearest is engagement.prospect, which is a pre-contract state",
      "replacement": "engagement.prospect"
    },
    "Letter sent": {
      "object": "envelope",
      "code": "sent"
    },
    "Active": {
      "object": "engagement",
      "code": "active"
    },
    "On hold": {
      "object": "engagement",
      "code": "on_hold"
    },
    "Complete": {
      "object": "engagement",
      "code": "delivered"
    },
    "Archived": {
      "object": "engagement",
      "code": "archived"
    }
  },
  "Tax return": {
    "Not started": {
      "object": "return",
      "code": "not_started"
    },
    "Waiting on client": {
      "object": "card_overlay",
      "code": "waiting_on_client"
    },
    "Preparing": {
      "object": "return",
      "code": "preparing"
    },
    "Working": {
      "object": "return",
      "code": "preparing"
    },
    "Processing": {
      "object": "agent_run",
      "code": "running"
    },
    "In review": {
      "object": "return",
      "code": "in_review"
    },
    "Ready to file": {
      "object": "return",
      "code": "approved"
    },
    "Transmitted": {
      "object": "return",
      "code": "filed"
    },
    "Accepted": {
      "object": "return",
      "code": "accepted"
    },
    "Rejected": {
      "object": "return",
      "code": "rejected"
    },
    "Filed": {
      "object": "return",
      "code": "filed"
    },
    "Extended": {
      "object": "return_flag",
      "code": "extended"
    }
  },
  "Return sync chip": {
    "Not yet exported": {
      "object": "return_sync_chip",
      "code": "not_yet_exported"
    },
    "Ready for export": {
      "object": "return_sync_chip",
      "code": "ready_for_export"
    },
    "Exporting": {
      "object": "return_sync_chip",
      "code": "exporting"
    },
    "Synced": {
      "object": "return_sync_chip",
      "code": "synced"
    },
    "Out of sync": {
      "object": "return_sync_chip",
      "code": "out_of_sync"
    },
    "Import pending approval": {
      "object": "return_sync_chip",
      "code": "import_pending_approval"
    },
    "Export failed": {
      "object": "return_sync_chip",
      "code": "failed"
    }
  },
  "Document": {
    "Requested": {
      "object": "request",
      "code": "requested"
    },
    "Received": {
      "object": "request",
      "code": "uploaded"
    },
    "Processing": {
      "object": "document",
      "code": "processing"
    },
    "Needs review": {
      "object": "document",
      "code": "classified"
    },
    "Approved": {
      "object": "document",
      "code": "approved"
    },
    "Rejected": {
      "object": "document",
      "code": "rejected"
    },
    "Duplicate": {
      "retired": true,
      "reason": "no Duplicate state in 3.3.1; a duplicate is a flag on a document, not a lifecycle state",
      "replacement": null
    },
    "Superseded": {
      "object": "document",
      "code": "superseded"
    }
  },
  "Audit": {
    "Not started": {
      "retired": true,
      "reason": "no pre-Planning state on the audit engagement record in 3.3.1",
      "replacement": null
    },
    "Planning": {
      "object": "audit_engagement",
      "code": "planning"
    },
    "Processing": {
      "object": "audit_engagement",
      "code": "processing"
    },
    "Fieldwork": {
      "object": "audit_engagement",
      "code": "fieldwork"
    },
    "Completion": {
      "object": "audit_engagement",
      "code": "completion"
    },
    "In review": {
      "object": "audit_engagement",
      "code": "in_review"
    },
    "Ready to issue": {
      "object": "audit_engagement",
      "code": "ready_to_release"
    },
    "Issued": {
      "object": "audit_engagement",
      "code": "released"
    },
    "Archived": {
      "object": "audit_engagement",
      "code": "archived"
    }
  },
  "Audit section": {
    "Queued": {
      "object": "audit_section",
      "code": "queued"
    },
    "Running": {
      "object": "audit_section",
      "code": "running"
    },
    "In progress": {
      "object": "audit_section",
      "code": "in_progress"
    },
    "Waiting on inputs": {
      "object": "audit_section",
      "code": "waiting_on_inputs"
    },
    "Blocked": {
      "object": "audit_section",
      "code": "blocked_on_decision"
    },
    "Ready": {
      "object": "audit_section",
      "code": "ready_to_run"
    },
    "Complete": {
      "object": "audit_section",
      "code": "draft_ready"
    },
    "Exceptions": {
      "retired": true,
      "reason": "a count line ({n} exceptions found), not a state; exceptions live on control_test_result / issue",
      "replacement": null
    },
    "Failed": {
      "object": "audit_section",
      "code": "failed"
    },
    "Skipped": {
      "retired": true,
      "reason": "no Skipped state in 3.3.1",
      "replacement": null
    }
  },
  "Workpaper": {
    "Not started": {
      "object": "audit_section",
      "code": "not_started"
    },
    "In progress": {
      "object": "audit_section",
      "code": "in_progress"
    },
    "Prepared": {
      "object": "audit_section",
      "code": "prepared"
    },
    "Review notes": {
      "object": "review_note",
      "code": "open"
    },
    "Reviewed": {
      "object": "audit_section",
      "code": "reviewed"
    },
    "Not applicable": {
      "retired": true,
      "reason": "no Not applicable state on a section or workpaper in 3.3.1",
      "replacement": null
    }
  },
  "Close": {
    "Not started": {
      "object": "close",
      "code": "not_started"
    },
    "In progress": {
      "object": "close",
      "code": "in_progress"
    },
    "In review": {
      "object": "close",
      "code": "in_review"
    },
    "Reopened": {
      "retired": true,
      "reason": "3.3.1 has no reopen state; Locked is final (Approved, Delivered, Locked)",
      "replacement": null
    },
    "Closed": {
      "object": "close",
      "code": "locked"
    }
  },
  "Close task": {
    "Queued": {
      "object": "close_task",
      "code": "queued"
    },
    "Running": {
      "object": "close_task",
      "code": "running"
    },
    "Waiting on client": {
      "object": "card_overlay",
      "code": "waiting_on_client"
    },
    "Issues found": {
      "object": "close_task",
      "code": "needs_attention"
    },
    "No issues": {
      "object": "close_task",
      "code": "done"
    },
    "Reconciled": {
      "object": "close_task",
      "code": "done"
    },
    "Failed": {
      "object": "close_task",
      "code": "failed"
    },
    "Skipped": {
      "retired": true,
      "reason": "no Skipped state in 3.3.1",
      "replacement": null
    }
  },
  "Request": {
    "Draft": {
      "object": "request",
      "code": "draft"
    },
    "Sent": {
      "object": "request",
      "code": "requested"
    },
    "Viewed": {
      "retired": true,
      "reason": "a client view event, not a request state in 3.3.1",
      "replacement": null
    },
    "Answered": {
      "object": "request",
      "code": "uploaded"
    },
    "Overdue": {
      "object": "request",
      "code": "overdue"
    },
    "Closed": {
      "object": "request",
      "code": "received"
    },
    "Cancelled": {
      "retired": true,
      "reason": "no Cancelled state in 3.3.1; not_applicable means the request does not apply, not that it was cancelled",
      "replacement": null
    }
  },
  "Inbox item": {
    "Unprocessed": {
      "object": "inbox_item",
      "code": "new"
    },
    "Waiting": {
      "object": "inbox_item",
      "code": "waiting"
    },
    "Filed": {
      "object": "inbox_item",
      "code": "filed"
    },
    "Ignored": {
      "object": "inbox_item",
      "code": "ignored"
    }
  },
  "Issue": {
    "Open": {
      "object": "issue",
      "code": "open"
    },
    "Review point": {
      "retired": true,
      "reason": "a kind line on an open issue (3.3.1), not a state",
      "replacement": null
    },
    "Waiting on client": {
      "retired": true,
      "reason": "a kind line on an open issue (3.3.1); the Board overlay is card_overlay.waiting_on_client",
      "replacement": "card_overlay.waiting_on_client"
    },
    "Resolved": {
      "object": "issue",
      "code": "resolved"
    },
    "Dismissed": {
      "object": "issue",
      "code": "not_applicable"
    }
  },
  "Audit finding": {
    "Observation": {
      "retired": true,
      "reason": "no Observation state in 3.3.1",
      "replacement": null
    },
    "Deficiency": {
      "object": "deficiency_severity",
      "code": "deficiency"
    },
    "Significant deficiency": {
      "object": "deficiency_severity",
      "code": "significant_deficiency"
    },
    "Material weakness": {
      "object": "deficiency_severity",
      "code": "material_weakness"
    },
    "Corrected": {
      "object": "misstatement",
      "code": "booked"
    },
    "Uncorrected": {
      "object": "misstatement",
      "code": "confirmed"
    },
    "Passed": {
      "object": "misstatement",
      "code": "passed_on_sum"
    }
  },
  "Agent run": {
    "Queued": {
      "object": "agent_run",
      "code": "queued"
    },
    "Running": {
      "object": "agent_run",
      "code": "running"
    },
    "Waiting on you": {
      "object": "agent_run",
      "code": "needs_input"
    },
    "Complete": {
      "object": "agent_run",
      "code": "succeeded"
    },
    "Exceptions": {
      "retired": true,
      "reason": "an outcome count on a succeeded run, not a run state in 3.3.1",
      "replacement": null
    },
    "Failed": {
      "object": "agent_run",
      "code": "failed"
    },
    "Cancelled": {
      "object": "agent_run",
      "code": "cancelled"
    }
  },
  "AJE": {
    "Proposed": {
      "object": "proposed_entry",
      "code": "proposed"
    },
    "In review": {
      "object": "proposed_entry",
      "code": "review_required"
    },
    "Approved": {
      "object": "proposed_entry",
      "code": "approved"
    },
    "Posted": {
      "object": "proposed_entry",
      "code": "posted"
    },
    "Passed": {
      "object": "misstatement",
      "code": "passed_on_sum"
    },
    "Rejected": {
      "retired": true,
      "reason": "proposed_entry has Failed post but no Rejected in 3.3.1",
      "replacement": null
    },
    "Reversed": {
      "object": "proposed_entry",
      "code": "reversed"
    }
  },
  "Session": {
    "Running": {
      "object": "workbench_session",
      "code": "running"
    },
    "Waiting on you": {
      "object": "workbench_session",
      "code": "awaiting_answer"
    },
    "Paused": {
      "retired": true,
      "reason": "no Paused session state in 3.3.1",
      "replacement": null
    },
    "Done": {
      "object": "workbench_session",
      "code": "complete"
    },
    "Failed": {
      "object": "workbench_session",
      "code": "failed"
    },
    "Archived": {
      "retired": true,
      "reason": "no Archived session state in 3.3.1",
      "replacement": null
    }
  },
  "Agent template": {
    "Available": {
      "object": "agent_template",
      "code": "available"
    },
    "Installed": {
      "object": "agent_template",
      "code": "installed"
    },
    "Update available": {
      "object": "agent_template",
      "code": "update_available"
    },
    "Draft": {
      "retired": true,
      "reason": "agent_template has no Draft in 3.3.1 (template_version.draft is a different object)",
      "replacement": null
    },
    "Coming soon": {
      "object": "agent_template",
      "code": "coming_soon"
    },
    "Deprecated": {
      "retired": true,
      "reason": "agent_template has no Deprecated in 3.3.1 (template_version.deprecated is a different object)",
      "replacement": null
    }
  },
  "Integration": {
    "Available": {
      "object": "integration",
      "code": "available"
    },
    "Connecting": {
      "object": "integration",
      "code": "connecting"
    },
    "Connected": {
      "object": "integration",
      "code": "connected"
    },
    "Syncing": {
      "retired": true,
      "reason": "an activity on a connected integration, not a state in 3.3.1",
      "replacement": null
    },
    "Disconnected": {
      "object": "integration",
      "code": "disconnected"
    },
    "Coming soon": {
      "object": "integration",
      "code": "coming_soon"
    }
  },
  "Signature": {
    "Draft": {
      "object": "envelope",
      "code": "draft"
    },
    "Sent": {
      "object": "envelope",
      "code": "sent"
    },
    "Viewed": {
      "object": "envelope",
      "code": "viewed"
    },
    "Partially signed": {
      "object": "envelope",
      "code": "partially_signed"
    },
    "Signed": {
      "object": "envelope",
      "code": "completed"
    },
    "Declined": {
      "object": "envelope",
      "code": "declined"
    },
    "Expired": {
      "object": "envelope",
      "code": "expired"
    },
    "Voided": {
      "object": "envelope",
      "code": "voided"
    }
  },
  "Notice": {
    "New": {
      "object": "notice",
      "code": "received"
    },
    "Researching": {
      "object": "notice",
      "code": "analyzing"
    },
    "Response drafted": {
      "object": "notice",
      "code": "response_drafted"
    },
    "Responded": {
      "object": "notice",
      "code": "sent"
    },
    "Resolved": {
      "object": "notice",
      "code": "closed"
    },
    "Response overdue": {
      "retired": true,
      "reason": "overdue is derived from the respond-by date and never stored; notice has no overdue state",
      "replacement": null
    }
  },
  "Tally": {
    "Ties": {
      "object": "tie_out_tally",
      "code": "tie"
    },
    "Off": {
      "object": "tie_out_tally",
      "code": "off"
    },
    "Check": {
      "object": "tie_out_tally",
      "code": "check"
    },
    "Pending": {
      "object": "tie_out_tally",
      "code": "pending"
    }
  }
} as const;

// Codes and words retired from the repo and the design sources, with replacements.
export const RETIRED_CODES = {
  "request_item.open": {
    "replacement": [
      "request.draft",
      "request.requested"
    ],
    "note": "draft while firm-only; requested once sent to the client"
  },
  "request_item.received": {
    "replacement": [
      "request.uploaded"
    ],
    "note": "INVERSION: repo received meant uploaded; screening sub-state not_screened"
  },
  "request_item.ready_for_review": {
    "replacement": [
      "request.uploaded"
    ],
    "note": "screening sub-state passed"
  },
  "request_item.needs_revision": {
    "replacement": [
      "request.returned"
    ]
  },
  "request_item.accepted": {
    "replacement": [
      "request.received"
    ],
    "note": "Accrued received means accepted"
  },
  "engagement.active": {
    "replacement": [
      "engagement.active"
    ],
    "note": "unchanged"
  },
  "engagement.archived": {
    "replacement": [
      "engagement.archived"
    ],
    "note": "unchanged; display adds a lock"
  },
  "connection.active": {
    "replacement": [
      "integration.connected"
    ]
  },
  "connection.needs_attention": {
    "replacement": [
      "integration.needs_attention",
      "integration.needs_reauth"
    ],
    "note": "split on failure code token_expired / invalid_grant"
  },
  "connection.revoked": {
    "replacement": [
      "integration.disconnected"
    ],
    "note": "neutral, not red"
  },
  "agent_run.completed": {
    "replacement": [
      "agent_run.succeeded"
    ],
    "note": "display Ready for review"
  },
  "agent_run.escalated": {
    "replacement": [
      "agent_run.needs_input"
    ],
    "note": "reason: escalated"
  },
  "ui.workpaper.draft": {
    "replacement": [
      "audit_section.in_progress"
    ],
    "note": "inferred"
  },
  "ui.workpaper.ready": {
    "replacement": [
      "audit_section.prepared"
    ],
    "note": "inferred; app label Prepared"
  },
  "ui.result.supported": {
    "replacement": [
      "control_test_result.no_exceptions_noted"
    ],
    "note": "inferred"
  },
  "ui.result.exception": {
    "replacement": [
      "control_test_result.exceptions_noted"
    ],
    "note": "inferred"
  },
  "ui.decision.accept": {
    "replacement": [],
    "note": "a decision value, not a status; no registry home yet (accept/reject)"
  },
  "ui.decision.reject": {
    "replacement": [
      "card_overlay.sent_back"
    ],
    "note": "inferred from the label Sent back; confirm"
  }
} as const;
