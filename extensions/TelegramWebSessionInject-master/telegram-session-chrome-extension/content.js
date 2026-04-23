// Content script for Telegram Session Injector
// This script runs on web.telegram.org pages

console.log('Telegram Session Injector content script loaded');

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'injectSession') {
        injectSessionData(request.sessionData);
        sendResponse({
            success: true
        });
    }
    return true;
});

// Check if we have stored session data to inject on page load
chrome.storage.local.get(['sessionData'], (result) => {
    if (result.sessionData) {
        console.log('Found stored session data, attempting injection...');

        // Wait for page to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                setTimeout(() => injectSessionData(result.sessionData), 1000);
            });
        } else {
            setTimeout(() => injectSessionData(result.sessionData), 1000);
        }
    }
});

// Function to inject session data into localStorage
function injectSessionData(sessionData) {
    try {
        console.log('Injecting session data into Telegram Web:', sessionData);

        const {
            dcId,
            authKey,
            userId,
            serverAddress,
            port
        } = sessionData;

        // Clear existing session data properly (based on real Telegram Web localStorage structure)
        const keysToRemove = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && (
                    key.includes('auth_key') || // dc1_auth_key, dc4_auth_key, etc.
                    key.includes('server_salt') || // dc1_server_salt, dc4_server_salt, etc.
                    key === 'user_auth' || // user authentication data
                    key === 'dc' || // data center ID
                    key === 'server_time_offset' || // server time offset
                    key.startsWith('account') || // account1, account2, etc.
                    key === 'tgme_sync' // Telegram sync data
                )) {
                keysToRemove.push(key);
            }
        }

        console.log(`🧹 Clearing ${keysToRemove.length} existing session keys:`, keysToRemove);
        keysToRemove.forEach(key => {
            localStorage.removeItem(key);
            console.log(`  ❌ Removed: ${key}`);
        });

        // Set the auth key for the specific data center (wrapped in quotes, like in real Telegram Web localStorage)
        const authKeyName = `dc${dcId}_auth_key`;
        localStorage.setItem(authKeyName, `"${authKey}"`);
        console.log(`✅ Set ${authKeyName} (length: ${authKey.length})`);

        // Set user authentication data in correct format
        if (userId) {
            const userAuth = {
                dcID: dcId,
                id: userId.toString()
            };
            localStorage.setItem('user_auth', JSON.stringify(userAuth));
            console.log(`✅ Set user_auth:`, userAuth);
        }

        // Set data center info
        localStorage.setItem('dc', dcId.toString());
        console.log(`✅ Set dc: ${dcId}`);

        // Set server time offset
        localStorage.setItem('server_time_offset', '0');
        console.log(`✅ Set server_time_offset: 0`);

        // Set server salt (WITHOUT quotes, as plain HEX string like in real localStorage)
        const serverSalt = Array.from(crypto.getRandomValues(new Uint8Array(8)))
            .map(b => b.toString(16).padStart(2, '0'))
            .join('');
        localStorage.setItem(`dc${dcId}_server_salt`, `"${serverSalt}"`);
        console.log(`✅ Set dc${dcId}_server_salt: "${serverSalt}"`);

        // Create account data structure (like account1 in real localStorage)
        const accountData = {
            dcId: dcId,
            [`dc${dcId}_auth_key`]: authKey, // without quotes for account data
            [`dc${dcId}_server_salt`]: serverSalt,
            userId: userId ? userId.toString() : null
        };

        if (userId) {
            // Add additional user info if available (placeholder data)
            accountData.firstName = "User";
            accountData.lastName = "";
            accountData.isPremium = false;
            accountData.phone = null; // We don't have phone from session file
        }

        localStorage.setItem('account1', JSON.stringify(accountData));
        console.log(`✅ Set account1 data structure`);

        // Additional metadata keys to mimic a normal logged-in session
        try {
            // auth_key_fingerprint = first 8 hex chars of primary dc auth key (quoted)
            const fingerprint = authKey.substring(0, 8);
            localStorage.setItem('auth_key_fingerprint', `"${fingerprint}"`);
            console.log(`✅ Set auth_key_fingerprint: "${fingerprint}"`);

            // number_of_accounts (string) – assume single account
            localStorage.setItem('number_of_accounts', '1');
            // multitab marker
            localStorage.setItem('tt-multitab_1', '1');
            // loglevel (observed 'SILENT')
            localStorage.setItem('loglevel', 'SILENT');
            // build/version placeholders (optional)
            if (!localStorage.getItem('k_build')) {
                localStorage.setItem('k_build', '589');
            }
            if (!localStorage.getItem('kz_version')) {
                localStorage.setItem('kz_version', '"K"');
            }
            // state_id random 32-bit unsigned
            const stateId = Math.floor(Math.random() * 0xFFFFFFFF) >>> 0;
            localStorage.setItem('state_id', stateId.toString());
            // trust:cache:timestamp JSON with ms timestamp
            localStorage.setItem('trust:cache:timestamp', JSON.stringify({
                timestamp: Date.now()
            }));
            // xt_instance minimal structure
            localStorage.setItem('xt_instance', JSON.stringify({
                id: Math.floor(Math.random() * 1e8),
                idle: false,
                time: Date.now()
            }));
            // tgme_sync basic
            localStorage.setItem('tgme_sync', JSON.stringify({
                canRedirect: true,
                ts: Math.floor(Date.now() / 1000)
            }));
            console.log('✅ Set auxiliary session metadata keys');
        } catch (metaErr) {
            console.warn('⚠️ Failed setting some metadata keys:', metaErr);
        }

        console.log('🎯 Session injection completed successfully!');
        console.log('📋 Final localStorage structure:');
        console.log(`- ${authKeyName}: "${authKey.substring(0, 32)}..." (${authKey.length} chars)`);
        console.log(`- user_auth: dcID=${dcId}, id=${userId}`);
        console.log(`- dc: ${dcId}`);
        console.log(`- dc${dcId}_server_salt: "${serverSalt}"`);
        console.log(`- server_time_offset: 0`);
        console.log(`- account1: complete account structure`);
        console.log(`- auth_key_fingerprint: first 8 chars -> ${authKey.substring(0,8)}`);

        // Clear the stored session data since we've used it
        chrome.storage.local.remove(['sessionData']);

        console.log('Session injection completed. Current localStorage keys:', Object.keys(localStorage));

        // Notify that injection is complete and reload the page
        setTimeout(() => {
            console.log('Reloading page to apply session...');
            window.location.reload();
        }, 1000);

        return true;

    } catch (error) {
        console.error('Failed to inject session data:', error);
        return false;
    }
}

// Monitor for successful authentication
function monitorAuthentication() {
    const checkAuth = () => {
        // Check if user is authenticated by looking for specific elements or localStorage
        // TODO: Implement better checking
        const userAuth = localStorage.getItem('user_auth');
        if (userAuth) {
            console.log('User appears to be authenticated:', userAuth);

            // Send success message to popup if it's open
            chrome.runtime.sendMessage({
                action: 'authSuccess',
                data: {
                    authenticated: true
                }
            }).catch(() => {
                // Popup might not be open, ignore error
            });
        }
    };

    setTimeout(checkAuth, 3000);
    setTimeout(checkAuth, 10000);
}

// Start monitoring
monitorAuthentication();

function debugLocalStorage() {
    console.log('Current localStorage contents:');
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        const value = localStorage.getItem(key);
        console.log(`${key}: ${value.length > 100 ? value.substring(0, 100) + '...' : value}`);
    }
}

// Export debug function to global scope for manual testing
window.debugTelegramSession = debugLocalStorage;