# Code Database for Automated Development

*Note: This is a pre-alpha release, and the system is in a very early, brittle state. Use at your own risk.*

## Overview

This repository contains a Python-based code management system designed to streamline the development process in Julia. It focuses on managing function definitions, running unit tests, tracking modifications, and maintaining a versioned log of results. The goal is to provide a structured yet flexible approach to handling changes at the function level.

### Key Features
- **Function Management:** The system is built around the idea of managing functions as the smallest unit of code. Instead of working with entire files, functions and their associated metadata (such as input/output types, tests, and documentation) are stored in a database. This enables atomic changes and continuous testing. Given that Julia primarily revolves around structs and functions, this method aligns perfectly with its design philosophy. The long-term plan is to allow interaction with individual functions, either directly or through a language model of your choice.
  
- **Unit Testing:** Each function can have associated unit tests, which are automatically executed upon modification. The results are logged, providing detailed statuses such as "Passed" or "Failed."

- **Modification Logging:** The system logs all changes made to the code, including information about who made the changes, when they occurred, and what was modified.

- **Test Results:** The outcome of each unit test is stored in a log, allowing for further analysis, including execution dates and test statuses.

## License

This project is licensed under the Unlicense.

## Contribution

Contributions are welcome! Feel free to submit issues or pull requests to help improve the system.
