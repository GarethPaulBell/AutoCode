# Code Database for Automated Development
Note: This is AI generated slop at the moment, and very brittle/ PRE ALPHA

*Use at your own risk*

## Overview

This repository contains a Python-based code management system for Julia designed to streamline the process of managing function definition, unit testing, and tracking modifications. It provides the ability to create functions, add unit tests, execute those tests, and log modifications to code with versioning and result tracking.

### Key Features
- **Function Management:** The philosiphy of this system is to work at the level of functions as the smallest possible unit rather than files, track changes to these, and then continuously test any changes. Each function and assocated Meta Data are stored (input and output types, tests, documentation etc.) in a database rather than a text file allowing for more atomic changes, or at least that is the plan. Julia only really has structs and functions and so is perfect for this approach. Moving forward, the intention is that you can interact with each function personally or with the LLM of your choice.
- **Unit Testing:** Associate unit tests with functions. These tests are automatically executed, and results are tracked with detailed statuses (Passed, Failed, etc.).
- **Modification Logging:** Track all modifications to the code, including details about who modified it, when, and the nature of the changes.
- **Test Results:** Logs the outcome of unit tests for further analysis, including execution dates and statuses.


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contribution

Feel free to submit issues or pull requests to improve the system.

