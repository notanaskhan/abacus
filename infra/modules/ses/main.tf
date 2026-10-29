# SES for the environment (Q-01-T46; P3): a configuration set whose delivery events land on an
# SQS queue the app drains (ses_events_queue_url). Staging stays in the SES sandbox with one
# verified address until the firm sender domain and DKIM exist (DEC-1003): AWS emails that address
# a link the builder clicks once.

resource "aws_sesv2_configuration_set" "this" {
  configuration_set_name = "abacus-${var.environment}"

  delivery_options {
    tls_policy = "REQUIRE"
  }

  reputation_options {
    reputation_metrics_enabled = true
  }
}

resource "aws_sesv2_email_identity" "address" {
  count                  = var.verified_address == null ? 0 : 1
  email_identity         = var.verified_address
  configuration_set_name = aws_sesv2_configuration_set.this.configuration_set_name
}

resource "aws_sqs_queue" "events" {
  name                      = "abacus-${var.environment}-ses-events"
  message_retention_seconds = 345600
  kms_master_key_id         = var.kms_key_arn
}

resource "aws_sns_topic" "events" {
  name              = "abacus-${var.environment}-ses-events"
  kms_master_key_id = var.kms_key_arn
}

resource "aws_sns_topic_subscription" "events" {
  topic_arn            = aws_sns_topic.events.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.events.arn
  raw_message_delivery = true
}

data "aws_iam_policy_document" "queue" {
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.events.arn]

    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_sns_topic.events.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "events" {
  queue_url = aws_sqs_queue.events.id
  policy    = data.aws_iam_policy_document.queue.json
}

resource "aws_sesv2_configuration_set_event_destination" "events" {
  configuration_set_name = aws_sesv2_configuration_set.this.configuration_set_name
  event_destination_name = "delivery-events"

  event_destination {
    enabled              = true
    matching_event_types = ["SEND", "DELIVERY", "BOUNCE", "COMPLAINT", "REJECT"]

    sns_destination {
      topic_arn = aws_sns_topic.events.arn
    }
  }
}
