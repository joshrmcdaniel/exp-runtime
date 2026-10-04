# v0.1.3

## Added

- Episode surveys now show “Thanks for taking the survey!” locally and continue
  any remaining story, without sending responses to a server. Saves stopped at
  survey submission recover without repeating the questions.

## Fixed

- Implemented Android's randomized choice order. Choices preserve
  their script return values and saved random state. Existing saves stopped
  there now resume without replaying earlier progress or reimporting content.
