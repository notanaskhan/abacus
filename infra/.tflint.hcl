# tflint with the bundled terraform ruleset only (no plugins to download).
config {
  call_module_type = "local"
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}
