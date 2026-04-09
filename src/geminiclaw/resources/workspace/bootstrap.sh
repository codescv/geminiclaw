#!/bin/bash
if [ "$(uname -s)" = "Darwin" ]; then
  SEATBELT_PROFILE=geminiclaw GEMINI_CLI_HOME=. gemini --sandbox
else
  GEMINI_CLI_HOME=. gemini
fi