import Foundation
import Security
import CryptoKit

enum TastesConfiguration {
    static let siteURL = URL(string: "https://152.234.209.214/")!
    static let group = "group.com.krotkovkirill.DifferentTastes"
    static let widgetKind = "DifferentTastesLatest"
    static let feedLink = URL(string: "differenttastes://feed")!
    static let setupLink = URL(string: "differenttastes://setup")!
}

struct LatestPost: Codable {
    let id: Int
    let username: String
    let rating: Int
    let comment: String
    let createdAt: String
    let imageData: Data?
    enum CodingKeys: String, CodingKey {
        case id, username, rating, comment
        case createdAt = "created_at"
        case imageData = "image_base64"
    }
}

struct LatestFeed: Codable {
    let post: LatestPost?
    let feedURL: URL
    enum CodingKeys: String, CodingKey {
        case post
        case feedURL = "feed_url"
    }
}

enum ConnectionError: Error {
    case invalidCode, unauthorized, invalidResponse, storage(OSStatus)
}

enum LatestFeedAPI {
    static func fetch(code: String) async throws -> LatestFeed {
        guard code.count == 43, code.range(of: "^[A-Za-z0-9_-]{43}$", options: .regularExpression) != nil else {
            throw ConnectionError.invalidCode
        }
        let url = TastesConfiguration.siteURL.appendingPathComponent("api").appendingPathComponent("widget").appendingPathComponent("latest")
        var request = URLRequest(url: url)
        request.setValue("Bearer \(code)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 20
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        let session = URLSession(configuration: config)
        defer { session.finishTasksAndInvalidate() }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw ConnectionError.invalidResponse }
        if http.statusCode == 401 { throw ConnectionError.unauthorized }
        guard http.statusCode == 200, data.count <= 1_048_576 else { throw ConnectionError.invalidResponse }
        let decoder = JSONDecoder()
        decoder.dataDecodingStrategy = .base64
        let result = try decoder.decode(LatestFeed.self, from: data)
        if let post = result.post, !(1...5).contains(post.rating) { throw ConnectionError.invalidResponse }
        return result
    }
}

enum SharedConnection {
    private static func query() -> [String: Any] {
        var values: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                    kSecAttrService as String: "DifferentTastes.Widget",
                                    kSecAttrAccount as String: "connection"]
        if let group = Bundle.main.object(forInfoDictionaryKey: "SharedKeychainAccessGroup") as? String, !group.isEmpty {
            values[kSecAttrAccessGroup as String] = group
        }
        return values
    }
    static func read() throws -> String? {
        var values = query()
        values[kSecReturnData as String] = true
        values[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(values as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data, let code = String(data: data, encoding: .utf8) else {
            throw ConnectionError.storage(status)
        }
        return code
    }
    static func save(_ code: String) throws {
        let data = Data(code.utf8)
        let updated = SecItemUpdate(query() as CFDictionary, [kSecValueData as String: data] as CFDictionary)
        if updated == errSecSuccess { return }
        guard updated == errSecItemNotFound else { throw ConnectionError.storage(updated) }
        var values = query()
        values[kSecValueData as String] = data
        values[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(values as CFDictionary, nil)
        guard status == errSecSuccess else { throw ConnectionError.storage(status) }
    }
    static func remove() throws {
        let status = SecItemDelete(query() as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else { throw ConnectionError.storage(status) }
    }
}

struct FeedCache: Codable {
    let date: Date
    let fingerprint: String
    let feed: LatestFeed
}

enum SharedFeedCache {
    private static var fileURL: URL? {
        FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: TastesConfiguration.group)?
            .appendingPathComponent("latest-feed.json")
    }
    private static func fingerprint(_ code: String) -> String {
        SHA256.hash(data: Data(code.utf8)).map { String(format: "%02x", $0) }.joined()
    }
    static func save(_ feed: LatestFeed, code: String) throws {
        guard let file = fileURL else { return }
        let data = try JSONEncoder().encode(FeedCache(date: Date(), fingerprint: fingerprint(code), feed: feed))
        var options: Data.WritingOptions = [.atomic]
        #if os(iOS)
        options.insert(.completeFileProtectionUntilFirstUserAuthentication)
        #endif
        try data.write(to: file, options: options)
    }
    static func read(code: String) -> LatestFeed? {
        guard let file = fileURL, let data = try? Data(contentsOf: file), data.count <= 1_048_576,
              let saved = try? JSONDecoder().decode(FeedCache.self, from: data),
              saved.fingerprint == fingerprint(code), (0...86400).contains(Date().timeIntervalSince(saved.date)) else { return nil }
        return saved.feed
    }
    static func remove() {
        if let file = fileURL { try? FileManager.default.removeItem(at: file) }
    }
}
