/**
 * Unit Test Suite for Chrome Extension Authentication & Account Switching Flow
 */
const assert = require('assert');

// Mock chrome API globals
let cachedTokens = {};
let lastErrorMsg = null;

global.chrome = {
  runtime: {
    get lastError() {
      return lastErrorMsg ? { message: lastErrorMsg } : null;
    }
  },
  identity: {
    getRedirectURL: (path) => {
      return "https://mock-extension-id.chromiumapp.org/";
    },
    launchWebAuthFlow: (options, callback) => {
      const authError = cachedTokens.launchWebAuthFlowError || cachedTokens.interactiveError;
      if (authError) {
        lastErrorMsg = authError;
        callback(null);
        lastErrorMsg = null;
        return;
      }
      const token = cachedTokens.activeToken || "mock_token_123";
      // Parse state from auth url
      const parsed = new URL(options.url);
      const state = parsed.searchParams.get("state") || "valid_state";
      assert.strictEqual(parsed.searchParams.get("prompt"), "select_account", "OAuth URL must include prompt=select_account");
      const redirectUrl = `https://mock-extension-id.chromiumapp.org/#access_token=${token}&token_type=Bearer&expires_in=3600&state=${state}`;
      callback(redirectUrl);
    },
    getAuthToken: (options, callback) => {
      if (options.interactive) {
        if (cachedTokens.interactiveError) {
          lastErrorMsg = cachedTokens.interactiveError;
          callback(null);
          lastErrorMsg = null;
          return;
        }
        const token = cachedTokens.activeToken || "mock_token_123";
        cachedTokens.cachedToken = token;
        callback(token);
      } else {
        if (cachedTokens.cachedToken) {
          callback(cachedTokens.cachedToken);
        } else {
          lastErrorMsg = "The user is not signed in.";
          callback(null);
          lastErrorMsg = null;
        }
      }
    },
    removeCachedAuthToken: (details, callback) => {
      delete cachedTokens.cachedToken;
      callback();
    },
    clearAllCachedAuthTokens: (callback) => {
      cachedTokens = {};
      callback();
    }
  }
};

// Mock fetch global
let mockFetchHandler = null;
global.fetch = async (url, options) => {
  if (mockFetchHandler) {
    return mockFetchHandler(url, options);
  }
  if (url.includes("oauth2.googleapis.com/revoke")) {
    return { ok: true, status: 200, text: async () => "" };
  }
  if (url.includes("gmail.googleapis.com/gmail/v1/users/me/profile")) {
    const authHeader = options?.headers?.Authorization || "";
    if (authHeader.includes("mock_token_userA")) {
      return { ok: true, status: 200, json: async () => ({ emailAddress: "userA@gmail.com" }) };
    }
    if (authHeader.includes("mock_token_userB")) {
      return { ok: true, status: 200, json: async () => ({ emailAddress: "userB@gmail.com" }) };
    }
    if (authHeader.includes("mock_token_invalid")) {
      return { ok: false, status: 401, json: async () => ({ error: "Unauthorized" }) };
    }
    return { ok: true, status: 200, json: async () => ({ emailAddress: "userA@gmail.com" }) };
  }
  return { ok: true, status: 200, json: async () => ({}) };
};

// Load compiled google-auth functions
const path = require('path');
const googleAuth = require(path.join(__dirname, 'dist', 'auth', 'google-auth.js'));

async function runTests() {
  console.log("=== Running Authentication & Account Switching Tests ===");

  // 1. Initial Gmail connection
  cachedTokens = { activeToken: "mock_token_userA" };
  const token1 = await googleAuth.signIn();
  assert.strictEqual(token1, "mock_token_userA");
  const user1 = await googleAuth.getCurrentUser(token1);
  assert.strictEqual(user1.email, "userA@gmail.com");
  const isAuth1 = await googleAuth.isAuthenticated();
  assert.strictEqual(isAuth1, true, "Initial connection should be authenticated");
  console.log("[PASS] Test 1: Initial Gmail connection");

  // 2. Disconnect with an existing token
  await googleAuth.signOut();
  const isAuth2 = await googleAuth.isAuthenticated();
  assert.strictEqual(isAuth2, false, "After disconnect, isAuthenticated must return false");
  console.log("[PASS] Test 2: Disconnect with existing token");

  // 3. Disconnect when no token exists
  await googleAuth.signOut(); // Should complete safely without error
  const isAuth3 = await googleAuth.isAuthenticated();
  assert.strictEqual(isAuth3, false);
  console.log("[PASS] Test 3: Disconnect when no token exists");

  // 4. Token revocation failure followed by cache cleanup
  cachedTokens = { activeToken: "mock_token_userA" };
  await googleAuth.signIn();
  mockFetchHandler = (url) => {
    if (url.includes("revoke")) throw new Error("Network offline");
    return { ok: true, status: 200, json: async () => ({ emailAddress: "userA@gmail.com" }) };
  };
  await googleAuth.signOut(); // Revocation throws, but cache cleanup must still proceed
  mockFetchHandler = null;
  const isAuth4 = await googleAuth.isAuthenticated();
  assert.strictEqual(isAuth4, false, "Cache cleanup must succeed even if server revocation network call fails");
  console.log("[PASS] Test 4: Token revocation failure fallback cache cleanup");

  // 5. Connecting the same account again
  cachedTokens = { activeToken: "mock_token_userA" };
  const tokenSame = await googleAuth.signIn();
  const userSame = await googleAuth.getCurrentUser(tokenSame);
  assert.strictEqual(userSame.email, "userA@gmail.com");
  console.log("[PASS] Test 5: Connecting the same account again");

  // 6. Connecting a different account after disconnect
  await googleAuth.signOut();
  cachedTokens = { activeToken: "mock_token_userB" };
  const tokenDiff = await googleAuth.signIn();
  const userDiff = await googleAuth.getCurrentUser(tokenDiff);
  assert.strictEqual(userDiff.email, "userB@gmail.com", "Should successfully connect account B after disconnect");
  console.log("[PASS] Test 6: Connecting a different account after disconnect");

  // 7. Cancelled OAuth authorization
  await googleAuth.signOut();
  cachedTokens = { interactiveError: "User denied OAuth permission" };
  try {
    await googleAuth.signIn();
    assert.fail("Should have thrown error on cancelled OAuth");
  } catch (err) {
    assert(err.message.includes("User denied OAuth permission"));
  }
  console.log("[PASS] Test 7: Cancelled OAuth authorization handling");

  // 8. Failed profile retrieval
  cachedTokens = { activeToken: "mock_token_invalid" };
  try {
    const tokenInvalid = await googleAuth.signIn();
    await googleAuth.getCurrentUser(tokenInvalid);
    assert.fail("Should throw on failed profile retrieval");
  } catch (err) {
    assert(err.message.includes("Failed to fetch Gmail account profile"));
  }
  console.log("[PASS] Test 8: Failed profile retrieval handling");

  // 9. Verify prompt=select_account is included in launchWebAuthFlow
  await googleAuth.signOut();
  cachedTokens = { activeToken: "mock_token_userB" };
  const tokenSelect = await googleAuth.launchWebAuthFlowAccountSelection();
  assert.strictEqual(tokenSelect, "mock_token_userB");
  const userSelect = await googleAuth.getCurrentUser(tokenSelect);
  assert.strictEqual(userSelect.email, "userB@gmail.com");
  console.log("[PASS] Test 9: Explicit account-selection flow with prompt=select_account");

  // 10. Tampered state parameter in redirect URL is rejected
  await googleAuth.signOut();
  const origLaunch = global.chrome.identity.launchWebAuthFlow;
  global.chrome.identity.launchWebAuthFlow = (options, callback) => {
    callback("https://mock-extension-id.chromiumapp.org/#access_token=spoofed_token&state=tampered_state");
  };
  try {
    await googleAuth.launchWebAuthFlowAccountSelection();
    assert.fail("Tampered state must be rejected");
  } catch (err) {
    assert(err.message.includes("state validation mismatch"));
  }
  global.chrome.identity.launchWebAuthFlow = origLaunch;
  console.log("[PASS] Test 10: Tampered state parameter correctly rejected");

  console.log("\n>>> ALL 10 AUTHENTICATION & ACCOUNT SWITCHING TESTS PASSED! <<<\n");
}

runTests().catch((err) => {
  console.error("Test failure:", err);
  process.exit(1);
});
