# Telegram Web Session Inject

## Description

This is a Chrome extension that allows you to import Telegram sessions from `.session` files into Telegram Web. It parses the SQLite database file, extracts authentication data, and injects it into Telegram Web's localStorage for seamless login.

## Features

- Import Telegram session from `.session` files (created by Telethon, Pyrogram, etc.)
- Parse SQLite database to extract auth keys, data center info, and user data
- Inject session data into Telegram Web **A version** localStorage
- Clear existing session data before importing new one
- Debug tools for troubleshooting

## Current Status

| Feature | Status | Notes |
|---------|--------|-------|
| Import session from .session file | ⚠️ Partially implemented | Works with Telethon/Pyrogram .session files, but needs thorough testing |
| Inject into Telegram Web A version | ✅ Implemented | Specifically targets web.telegram.org/a/ for compatibility. K version not supported - causes errors |
| Export current session to .session | ❌ Not implemented | Planned for future releases |
| Session cleanup before injection | ⚠️ Partially implemented | Clears localStorage, but may not work completely in all cases |
| Debug tools | ✅ Implemented | Built-in debug panel for troubleshooting |
| Cross-browser support | ❌ Not implemented | Chrome only currently |
| Session management UI | ❌ Not implemented | Single session injection only |

## Installation

1. Download or clone this repository.
2. Open Google Chrome and go to `chrome://extensions/`.
3. Enable "Developer mode" in the top right corner.
4. Click "Load unpacked" and select the `telegram-session-chrome-extension` folder from this project.
5. The extension should now be installed and visible in your extensions list.

## Usage

1. Open Telegram Web A version in a new tab (web.telegram.org/a/)
   
   ⚠️ **Important**: 
   - Use incognito mode for best results
   - Make sure you're not logged into Telegram Web in your regular browser
   - This prevents conflicts with existing sessions

2. Click on the extension icon in the Chrome toolbar.
3. Select your `.session` file (from Telethon/Pyrogram or similar libraries).
4. Click "🚀 Import Session" to parse and extract authentication data.
5. The extension will inject the session - you'll be automatically logged in.

**Important**: The extension works specifically with Telegram Web A version (web.telegram.org/a/) for session injection compatibility. K version is not supported and may cause errors.

## Future Plans (TODO)

- **Export Current Session**: Add the ability to export the current Telegram Web session to a `.session` file. This would allow users to backup their active sessions.
- **Support for K version**: Fix compatibility issues with Telegram Web K version (web.telegram.org/k/) to work alongside A version.
- **Improved Session Cleanup**: Enhance the session cleanup process when importing new sessions. Currently, it clears localStorage, but may not work completely in all cases.
- **Better Error Handling**: Add more detailed error messages and recovery options.
- **Cross-Browser Support**: Extend support to other browsers like Firefox.
- **Session Management UI**: Add interface to manage multiple sessions, switch between them, or delete old ones.

## Contributing

We welcome contributions from everyone! Here's how you can help:

### Ways to Contribute
- **Report Bugs**: Open an issue on GitHub with detailed information about the problem
- **Suggest Features**: Share your ideas for new functionality
- **Code Contributions**: Submit pull requests with improvements or fixes
- **Documentation**: Help improve this README or add code comments

### Guidelines
- Keep code clean and well-documented
- Test your changes thoroughly
- Update documentation if you add new features
- Be respectful and constructive in discussions

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0). 

### What this means:
- ✅ You can freely use, modify, and distribute this software
- ✅ Commercial use is allowed
- ✅ You must keep derivative works under GPL-3.0
- ✅ You must include the original copyright notice
- ✅ You must disclose source code for modified versions

For the full license text, see the [LICENSE](LICENSE) file.

### Why GPL?
GPL ensures that this project remains free and open-source. Any improvements or modifications must be shared back with the community, preventing proprietary forks that could harm the project's openness.

If you have questions about the license or contributing, feel free to open an issue!