# NextcloudMultiDirOneWaySync

> A simple nextcloud sync tool to sync multiple remote folders into one single local folder

[![Badge](https://img.shields.io/badge/org-KEG_Amorbach-blue)](https://amorgym.de)
[![Badge](https://img.shields.io/github/v/release/TechnikKEG/NextcloudMultiDirOneWaySync)](https://github.com/TechnikKEG/NextcloudMultiDirOneWaySync/releases/latest)
[![Badge](https://img.shields.io/badge/license-MIT-blue)](https://github.com/TechnikKEG/NextcloudMultiDirOneWaySync/blob/master/LICENSE)

---

What is it? Long and complicated name, but essentially this syncs multiple nextcloud remote folders into one singular local one, merging the contents, and only in this direction. **This tool does not support syncing local to remote!**.

## How to use

1. Best practice: Create a virtual environment (`python3 -m venv .venv`) and activate it
2. Copy `.env.example` to `.env` and change the values according to your configuration
3. Run `sync.py --help` to see the command usage

## Contributing/Misc

- Code is formatted using black with default settings.
- If there is a missing feature, feel free to create a pull-request, but it would be a good idea to create an issue first to discuss the feature to avoid unnecessary work.
- Please create an issue if you encounter any bugs.