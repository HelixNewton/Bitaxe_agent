#include "config_api.h"

#include <Arduino.h>
#include <ArduinoJson.h>
#include <WebServer.h>
#include <WiFi.h>

#include "drivers/storage/nvMemory.h"
#include "drivers/storage/storage.h"

#if __has_include("config_api_local.h")
#include "config_api_local.h"
#endif

#ifndef CONFIG_API_WIFI_SSID
#define CONFIG_API_WIFI_SSID ""
#endif
#ifndef CONFIG_API_WIFI_PASSWORD
#define CONFIG_API_WIFI_PASSWORD ""
#endif
#ifndef CONFIG_API_POOL_URL
#define CONFIG_API_POOL_URL ""
#endif
#ifndef CONFIG_API_POOL_PORT
#define CONFIG_API_POOL_PORT 0
#endif
#ifndef CONFIG_API_POOL_PASSWORD
#define CONFIG_API_POOL_PASSWORD ""
#endif
#ifndef CONFIG_API_WALLET
#define CONFIG_API_WALLET ""
#endif
#ifndef CONFIG_API_TIMEZONE
#define CONFIG_API_TIMEZONE 99
#endif
#ifndef CONFIG_API_SAVE_STATS
#define CONFIG_API_SAVE_STATS false
#endif
#ifndef CONFIG_API_FORCE_DEFAULTS
#define CONFIG_API_FORCE_DEFAULTS false
#endif

extern TSettings Settings;
extern nvMemory nvMem;
extern uint32_t templates;
extern uint32_t Mhashes;
extern uint32_t totalKHashes;
extern uint32_t elapsedKHs;
extern uint64_t upTime;
extern volatile uint32_t shares;
extern volatile uint32_t valids;
extern double best_diff;

static WebServer configApiServer(80);
static bool configApiStarted = false;

static void addCors()
{
    configApiServer.sendHeader("Access-Control-Allow-Origin", "*");
    configApiServer.sendHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
    configApiServer.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    configApiServer.sendHeader("Cache-Control", "no-store");
}

static void sendJson(JsonDocument& doc, int status = 200)
{
    String body;
    serializeJson(doc, body);
    addCors();
    configApiServer.send(status, "application/json", body);
}

static void sendError(const char* message, int status = 400)
{
    StaticJsonDocument<192> doc;
    doc["ok"] = false;
    doc["error"] = message;
    sendJson(doc, status);
}

static void copySetting(char* target, size_t targetSize, const String& value)
{
    if (targetSize == 0) return;
    strncpy(target, value.c_str(), targetSize - 1);
    target[targetSize - 1] = '\0';
}

static bool hasText(const char* value)
{
    return value != nullptr && value[0] != '\0';
}

void applyConfigApiDefaults()
{
    bool hasFirmwareDefaults = hasText(CONFIG_API_WIFI_SSID)
        || hasText(CONFIG_API_POOL_URL)
        || hasText(CONFIG_API_WALLET);
    if (!hasFirmwareDefaults) {
        return;
    }

    bool hasStoredConfig = nvMem.loadConfig(&Settings);
    if (hasStoredConfig && !CONFIG_API_FORCE_DEFAULTS) {
        Serial.println("NerdMiner config API defaults skipped; stored config already exists.");
        return;
    }

    if (hasText(CONFIG_API_POOL_URL)) {
        Settings.PoolAddress = CONFIG_API_POOL_URL;
    }
    if (CONFIG_API_POOL_PORT > 0) {
        Settings.PoolPort = CONFIG_API_POOL_PORT;
    }
    if (hasText(CONFIG_API_POOL_PASSWORD)) {
        copySetting(Settings.PoolPassword, sizeof(Settings.PoolPassword), CONFIG_API_POOL_PASSWORD);
    }
    if (hasText(CONFIG_API_WALLET)) {
        copySetting(Settings.BtcWallet, sizeof(Settings.BtcWallet), CONFIG_API_WALLET);
    }
    if (CONFIG_API_TIMEZONE >= -12 && CONFIG_API_TIMEZONE <= 14) {
        Settings.Timezone = CONFIG_API_TIMEZONE;
    }
    Settings.saveStats = CONFIG_API_SAVE_STATS;

    bool saved = nvMem.saveConfig(&Settings);
    Serial.printf("NerdMiner config API defaults %s.\n", saved ? "saved" : "could not be saved");

    if (hasText(CONFIG_API_WIFI_SSID)) {
        WiFi.persistent(true);
        WiFi.mode(WIFI_STA);
        WiFi.begin(CONFIG_API_WIFI_SSID, CONFIG_API_WIFI_PASSWORD);
        Serial.println("NerdMiner config API started Wi-Fi from firmware defaults.");
    }
}

static void handleOptions()
{
    addCors();
    configApiServer.send(204);
}

static void handleGetConfig()
{
    StaticJsonDocument<640> doc;
    doc["ok"] = true;
    doc["api"] = "nerdminer-config-api";
    doc["version"] = 1;
    doc["PoolUrl"] = Settings.PoolAddress;
    doc["PoolPort"] = Settings.PoolPort;
    doc["BtcWallet"] = Settings.BtcWallet;
    doc["Timezone"] = Settings.Timezone;
    doc["SaveStats"] = Settings.saveStats;
    doc["hasPoolPassword"] = strlen(Settings.PoolPassword) > 0;
    doc["wifiConnected"] = WiFi.status() == WL_CONNECTED;
    doc["ip"] = WiFi.localIP().toString();
    sendJson(doc);
}

static void handleStatus()
{
    StaticJsonDocument<768> doc;
    doc["ok"] = true;
    doc["api"] = "nerdminer-config-api";
    doc["currentHashRate"] = (double)elapsedKHs;
    doc["temp"] = temperatureRead();
    doc["completedShares"] = shares;
    doc["valids"] = valids;
    doc["templates"] = templates;
    doc["totalMHashes"] = Mhashes;
    doc["totalKHashes"] = totalKHashes;
    doc["bestDiff"] = best_diff;
    doc["upTime"] = upTime;
    doc["PoolUrl"] = Settings.PoolAddress;
    doc["PoolPort"] = Settings.PoolPort;
    doc["wifiConnected"] = WiFi.status() == WL_CONNECTED;
    doc["ip"] = WiFi.localIP().toString();
    sendJson(doc);
}

static void handlePostConfig()
{
    if (!configApiServer.hasArg("plain")) {
        sendError("missing JSON body");
        return;
    }

    StaticJsonDocument<1024> input;
    DeserializationError error = deserializeJson(input, configApiServer.arg("plain"));
    if (error) {
        sendError("invalid JSON body");
        return;
    }

    if (input.containsKey("PoolUrl")) {
        Settings.PoolAddress = input["PoolUrl"].as<String>();
    }
    if (input.containsKey("PoolPort")) {
        int port = input["PoolPort"].as<int>();
        if (port < 1 || port > 65535) {
            sendError("PoolPort must be between 1 and 65535");
            return;
        }
        Settings.PoolPort = port;
    }
    if (input.containsKey("PoolPassword")) {
        copySetting(Settings.PoolPassword, sizeof(Settings.PoolPassword), input["PoolPassword"].as<String>());
    }
    if (input.containsKey("BtcWallet")) {
        copySetting(Settings.BtcWallet, sizeof(Settings.BtcWallet), input["BtcWallet"].as<String>());
    }
    if (input.containsKey("Timezone")) {
        int timezone = input["Timezone"].as<int>();
        if (timezone < -12 || timezone > 14) {
            sendError("Timezone must be between -12 and 14");
            return;
        }
        Settings.Timezone = timezone;
    }
    if (input.containsKey("SaveStats")) {
        Settings.saveStats = input["SaveStats"].as<bool>();
    }

    bool saved = nvMem.saveConfig(&Settings);
    bool restart = !input.containsKey("Restart") || input["Restart"].as<bool>();
    bool wifiChange = input.containsKey("SSID") && input["SSID"].as<String>().length() > 0;
    String ssid = wifiChange ? input["SSID"].as<String>() : "";
    String wifiPassword = input.containsKey("WifiPW") ? input["WifiPW"].as<String>() : "";

    StaticJsonDocument<384> output;
    output["ok"] = saved;
    output["saved"] = saved;
    output["restart"] = restart;
    output["wifiChange"] = wifiChange;
    output["message"] = saved ? "Configuration saved" : "Configuration save failed";
    sendJson(output, saved ? 200 : 500);

    if (wifiChange) {
        delay(250);
        WiFi.persistent(true);
        WiFi.mode(WIFI_STA);
        WiFi.disconnect(true, true);
        delay(250);
        WiFi.begin(ssid.c_str(), wifiPassword.c_str());
    }
    if (restart) {
        delay(1000);
        ESP.restart();
    }
}

void setupConfigApi()
{
    if (configApiStarted) return;
    configApiServer.on("/api/config", HTTP_OPTIONS, handleOptions);
    configApiServer.on("/api/config", HTTP_GET, handleGetConfig);
    configApiServer.on("/api/config", HTTP_POST, handlePostConfig);
    configApiServer.on("/api/status", HTTP_OPTIONS, handleOptions);
    configApiServer.on("/api/status", HTTP_GET, handleStatus);
    configApiServer.begin();
    configApiStarted = true;
    Serial.println("NerdMiner config API listening on port 80");
}

void configApiLoop()
{
    if (configApiStarted) {
        configApiServer.handleClient();
    }
}
