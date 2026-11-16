import Foundation

@main
struct ModelChecks {
    static func main() throws {
        let json = Data("""
        {"post":{"id":7,"username":"Друг","rating":5,"comment":"Вкусно","created_at":"2026-11-16 12:00:00","image_base64":"YWJj"},"feed_url":"https://152.234.209.214/"}
        """.utf8)
        let decoder = JSONDecoder()
        decoder.dataDecodingStrategy = .base64
        let feed = try decoder.decode(LatestFeed.self, from: json)
        precondition(feed.post?.id == 7)
        precondition(feed.post?.rating == 5)
        precondition(feed.post?.comment == "Вкусно")
        precondition(feed.post?.imageData == Data("abc".utf8))
        precondition(feed.feedURL == TastesConfiguration.siteURL)
        let cached = try decoder.decode(LatestFeed.self, from: JSONEncoder().encode(feed))
        precondition(cached.post?.imageData == feed.post?.imageData)
        let empty = try decoder.decode(LatestFeed.self, from: Data("{\"post\":null,\"feed_url\":\"https://152.234.209.214/\"}".utf8))
        precondition(empty.post == nil)
        let noPhoto = try decoder.decode(LatestFeed.self, from: Data("{\"post\":{\"id\":1,\"username\":\"Друг\",\"rating\":4,\"comment\":\"\",\"created_at\":\"\",\"image_base64\":null},\"feed_url\":\"https://152.234.209.214/\"}".utf8))
        precondition(noPhoto.post?.imageData == nil && noPhoto.post?.comment == "")
        print("Native widget API model checks passed")
    }
}
