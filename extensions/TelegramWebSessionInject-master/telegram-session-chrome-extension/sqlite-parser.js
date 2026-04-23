// SQLite parser using sql.js for proper database analysis
let SQL = null;
let sqlJsInitialized = false;

// Initialize sql.js
async function initializeSqlJs() {
    if (sqlJsInitialized && SQL) {
        return true;
    }

    try {
        console.log('Attempting to initialize sql.js...');

        // Check if sql.js is available
        if (typeof window.initSqlJs === 'undefined') {
            throw new Error('sql.js library not loaded - window.initSqlJs is undefined');
        }

        console.log('Found window.initSqlJs, initializing...');

        // Initialize with WASM
        SQL = await window.initSqlJs({
            locateFile: function (file) {
                console.log('Locating file:', file);
                if (file.endsWith('.wasm')) {
                    const wasmUrl = chrome.runtime.getURL('sql-wasm.wasm');
                    console.log('WASM URL:', wasmUrl);
                    return wasmUrl;
                }
                return file;
            }
        });

        sqlJsInitialized = true;
        console.log('sql.js initialized successfully');
        return true;

    } catch (error) {
        console.error('Failed to initialize sql.js:', error);
        sqlJsInitialized = false;
        SQL = null;
        throw error;
    }
}

// Parse session file with proper SQLite parsing
async function parseSessionFile(arrayBuffer) {
    try {
        // Initialize sql.js if not already done
        await initializeSqlJs();

        // Create database from ArrayBuffer
        const uint8Array = new Uint8Array(arrayBuffer);
        const db = new SQL.Database(uint8Array);

        console.log('SQLite database opened successfully');

        // Get database structure and data
        const analysis = await analyzeDatabase(db);

        // Extract session data from the analysis
        const sessionData = extractSessionData(analysis);

        // Close database
        db.close();

        return sessionData;

    } catch (error) {
        console.error('Failed to parse session file:', error);
        throw new Error(`SQLite parsing failed: ${error.message}`);
    }
}

// Analyze database structure and content
async function analyzeDatabase(db) {
    const analysis = {
        tables: {},
        metadata: {},
        rawData: {}
    };

    try {
        // Get all tables
        const tablesResult = db.exec("SELECT name FROM sqlite_master WHERE type='table'");

        if (tablesResult.length > 0) {
            const tables = tablesResult[0].values.map(row => row[0]);
            console.log('Found tables:', tables);

            // Analyze each table
            for (const tableName of tables) {
                analysis.tables[tableName] = await analyzeTable(db, tableName);
            }
        }

        // Get database metadata
        analysis.metadata = {
            pageSize: getDatabasePageSize(db),
            encoding: getDatabaseEncoding(db),
            version: getDatabaseVersion(db)
        };

        return analysis;

    } catch (error) {
        console.error('Database analysis failed:', error);
        throw error;
    }
}

// Analyze individual table
async function analyzeTable(db, tableName) {
    const tableInfo = {
        name: tableName,
        schema: [],
        data: [],
        rowCount: 0
    };

    try {
        // Get table schema
        const schemaResult = db.exec(`PRAGMA table_info(${tableName})`);
        if (schemaResult.length > 0) {
            tableInfo.schema = schemaResult[0].values.map(row => ({
                id: row[0],
                name: row[1],
                type: row[2],
                notNull: row[3],
                defaultValue: row[4],
                primaryKey: row[5]
            }));
        }

        // Get row count
        const countResult = db.exec(`SELECT COUNT(*) FROM ${tableName}`);
        if (countResult.length > 0) {
            tableInfo.rowCount = countResult[0].values[0][0];
        }

        // Get actual data (limit to reasonable amount)
        const dataResult = db.exec(`SELECT * FROM ${tableName} LIMIT 100`);
        if (dataResult.length > 0) {
            tableInfo.data = {
                columns: dataResult[0].columns,
                values: dataResult[0].values
            };
        }

        console.log(`Table ${tableName}: ${tableInfo.rowCount} rows, ${tableInfo.schema.length} columns`);

        return tableInfo;

    } catch (error) {
        console.error(`Failed to analyze table ${tableName}:`, error);
        return {
            name: tableName,
            error: error.message,
            schema: [],
            data: [],
            rowCount: 0
        };
    }
}

// Extract session data from analysis
function extractSessionData(analysis) {
    console.log('Extracting session data from analysis...');

    let sessionData = {
        dc_id: null,
        auth_key: null,
        user_id: null,
        server_address: null,
        port: null
    };

    // Look for the sessions table specifically
    if (analysis.tables.sessions && analysis.tables.sessions.data) {
        const sessionsTable = analysis.tables.sessions;
        console.log('Found sessions table, extracting data...');

        if (Array.isArray(sessionsTable.data.values) && sessionsTable.data.values.length > 0) {
            const sessionRow = sessionsTable.data.values[0]; // First (and usually only) session
            const columns = sessionsTable.data.columns;

            for (let i = 0; i < columns.length && i < sessionRow.length; i++) {
                const columnName = columns[i].toLowerCase();
                const value = sessionRow[i];

                switch (columnName) {
                    case 'dc_id':
                        sessionData.dc_id = value;
                        console.log(`Found dc_id: ${value}`);
                        break;

                    case 'server_address':
                        sessionData.server_address = value;
                        console.log(`Found server_address: ${value}`);
                        break;

                    case 'port':
                        sessionData.port = value;
                        console.log(`Found port: ${value}`);
                        break;

                    case 'auth_key':
                        if (value && value instanceof Uint8Array) {
                            // auth_key is stored as BLOB, convert directly to Uint8Array
                            sessionData.auth_key = value;
                            console.log(`Found auth_key: ${value.length} bytes`);
                            console.log(`Auth key preview: ${Array.from(value.slice(0, 16)).map(b => b.toString(16).padStart(2, '0')).join('')}...`);
                        } else if (value && typeof value === 'object') {
                            // Convert the BLOB object to Uint8Array
                            const authKeyArray = new Uint8Array(256);
                            for (let j = 0; j < 256; j++) {
                                authKeyArray[j] = value[j.toString()] || 0;
                            }
                            sessionData.auth_key = authKeyArray;
                            console.log(`Found auth_key: ${authKeyArray.length} bytes`);
                            console.log(`Auth key preview: ${Array.from(authKeyArray.slice(0, 16)).map(b => b.toString(16).padStart(2, '0')).join('')}...`);
                        }
                        break;
                }
            }
        }
    }

    // Try to get user_id from entities table
    if (analysis.tables.entities && analysis.tables.entities.data) {
        const entitiesTable = analysis.tables.entities;
        console.log('Checking entities table for user_id...');

        if (Array.isArray(entitiesTable.data.values)) {
            for (const entityRow of entitiesTable.data.values) {
                if (Array.isArray(entityRow) && entityRow.length >= 6) {
                    const id = entityRow[0];
                    const phone = entityRow[3];
                    const name = entityRow[4];

                    // Look for the user's own entity (has phone number)
                    if (phone && phone !== 42777 && id && id !== 777000 && id !== 0) {
                        sessionData.user_id = id;
                        console.log(`Found user_id from entities: ${id} (phone: ${phone}, name: ${name})`);
                        break;
                    }
                }
            }
        }
    }

    // Validate that we found required data
    if (!sessionData.auth_key) {
        throw new Error('No auth_key found in session file');
    }

    if (!sessionData.dc_id) {
        throw new Error('No dc_id found in session file');
    }

    console.log('Session data extracted successfully:', {
        dc_id: sessionData.dc_id,
        auth_key_length: sessionData.auth_key ? sessionData.auth_key.length : 0,
        user_id: sessionData.user_id,
        server_address: sessionData.server_address,
        port: sessionData.port
    });

    return sessionData;
}

// Get detailed database analysis for debugging
async function getDetailedAnalysis(arrayBuffer) {
    try {
        await initializeSqlJs();

        const uint8Array = new Uint8Array(arrayBuffer);
        const db = new SQL.Database(uint8Array);

        const analysis = await analyzeDatabase(db);

        // Add some extra debugging info
        const debugInfo = {
            fileSize: arrayBuffer.byteLength,
            sqliteHeader: String.fromCharCode(...uint8Array.slice(0, 16)),
            pageSize: analysis.metadata.pageSize,
            encoding: analysis.metadata.encoding,
            version: analysis.metadata.version,
            tableCount: Object.keys(analysis.tables).length,
            tables: {}
        };

        // Format table information for debugging
        for (const [tableName, tableInfo] of Object.entries(analysis.tables)) {
            const sampleData = (tableInfo.data && Array.isArray(tableInfo.data.values)) ?
                tableInfo.data.values.slice(0, 3) : [];

            debugInfo.tables[tableName] = {
                rowCount: tableInfo.rowCount,
                columns: tableInfo.schema.map(col => `${col.name} (${col.type})`),
                sampleData: sampleData,
                error: tableInfo.error
            };
        }

        db.close();

        return {
            success: true,
            analysis: debugInfo,
            fullAnalysis: analysis
        };

    } catch (error) {
        return {
            success: false,
            error: error.message,
            stack: error.stack
        };
    }
}

// Helper functions
function getDatabasePageSize(db) {
    try {
        const result = db.exec("PRAGMA page_size");
        return result.length > 0 ? result[0].values[0][0] : 'unknown';
    } catch (error) {
        return 'error';
    }
}

function getDatabaseEncoding(db) {
    try {
        const result = db.exec("PRAGMA encoding");
        return result.length > 0 ? result[0].values[0][0] : 'unknown';
    } catch (error) {
        return 'error';
    }
}

function getDatabaseVersion(db) {
    try {
        const result = db.exec("PRAGMA user_version");
        return result.length > 0 ? result[0].values[0][0] : 'unknown';
    } catch (error) {
        return 'error';
    }
}

function hexStringToBytes(hexString) {
    // Remove any quotes or whitespace
    const cleanHex = hexString.replace(/[^0-9a-fA-F]/g, '');

    if (cleanHex.length % 2 !== 0) {
        throw new Error('Invalid hex string length');
    }

    const bytes = new Uint8Array(cleanHex.length / 2);
    for (let i = 0; i < cleanHex.length; i += 2) {
        bytes[i / 2] = parseInt(cleanHex.substr(i, 2), 16);
    }

    return bytes;
}

// Export functions for use in popup.js
window.parseSessionFile = parseSessionFile;
window.getDetailedAnalysis = getDetailedAnalysis;
window.initializeSqlJs = initializeSqlJs;