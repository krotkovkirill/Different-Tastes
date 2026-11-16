import WidgetKit
import SwiftUI
import UIKit

struct TasteEntry: TimelineEntry {
    let date: Date
    let post: LatestPost?
    let needsSetup: Bool
    let offline: Bool
}

struct LatestTasteProvider: TimelineProvider {
    func placeholder(in context: Context) -> TasteEntry {
        TasteEntry(date: Date(), post: LatestPost(id: 0, username: "Друг", rating: 5,
            comment: "Стоит попробовать", createdAt: "", imageData: nil), needsSetup: false, offline: false)
    }
    func getSnapshot(in context: Context, completion: @escaping (TasteEntry) -> Void) {
        if context.isPreview { completion(placeholder(in: context)); return }
        Task { completion(await entry()) }
    }
    func getTimeline(in context: Context, completion: @escaping (Timeline<TasteEntry>) -> Void) {
        Task {
            let value = await entry()
            completion(Timeline(entries: [value], policy: .after(Date().addingTimeInterval(20 * 60))))
        }
    }
    private func entry() async -> TasteEntry {
        guard let code = try? SharedConnection.read() else {
            return TasteEntry(date: Date(), post: nil, needsSetup: true, offline: false)
        }
        do {
            let feed = try await LatestFeedAPI.fetch(code: code)
            try? SharedFeedCache.save(feed, code: code)
            return TasteEntry(date: Date(), post: feed.post, needsSetup: false, offline: false)
        } catch ConnectionError.unauthorized {
            try? SharedConnection.remove()
            SharedFeedCache.remove()
            return TasteEntry(date: Date(), post: nil, needsSetup: true, offline: false)
        } catch {
            let cached = SharedFeedCache.read(code: code)
            return TasteEntry(date: Date(), post: cached?.post, needsSetup: false, offline: true)
        }
    }
}

struct LatestTasteView: View {
    @Environment(\.widgetFamily) private var family
    let entry: TasteEntry
    private var photo: UIImage? { entry.post?.imageData.flatMap { UIImage(data: $0) } }
    private var background: Color { Color(red: 0.99, green: 0.96, blue: 0.85) }
    var body: some View {
        Group {
            if let post = entry.post {
                if family == .systemMedium {
                    HStack(spacing: 14) {
                        photoView.frame(width: 125).clipped().clipShape(RoundedRectangle(cornerRadius: 16))
                        VStack(alignment: .leading, spacing: 8) {
                            Text(post.username).font(.caption.bold()).lineLimit(1)
                            Label("\(post.rating) / 5", systemImage: "star.fill").font(.headline).foregroundStyle(.orange)
                            if !post.comment.isEmpty { Text(post.comment).font(.callout).lineLimit(3) }
                            Spacer(minLength: 0)
                            footer
                        }.frame(maxWidth: .infinity, alignment: .leading)
                    }.padding(14)
                } else {
                    ZStack(alignment: .bottomLeading) {
                        photoView
                        LinearGradient(colors: [.clear, .black.opacity(0.82)], startPoint: .top, endPoint: .bottom)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(post.username).font(.caption.bold()).lineLimit(1)
                            Label("\(post.rating) / 5", systemImage: "star.fill").font(.headline)
                            if !post.comment.isEmpty { Text(post.comment).font(.caption).lineLimit(2) }
                            if entry.offline { Text("Сохранённая публикация").font(.caption2) }
                        }.foregroundStyle(.white).padding(13)
                    }
                }
            } else {
                VStack(alignment: .leading, spacing: 10) {
                    Image(systemName: entry.needsSetup ? "square.grid.2x2" : "camera").font(.title2)
                    Text(entry.needsSetup ? "Подключи виджет" : entry.offline ? "Нет соединения" : "Пока нет публикаций").font(.headline)
                    Text(entry.needsSetup ? "Открой Different Tastes" : "Нажми, чтобы открыть ленту").font(.caption).foregroundStyle(.secondary)
                }.padding(16).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
            }
        }
        .containerBackground(background, for: .widget)
        .widgetURL(entry.needsSetup ? TastesConfiguration.setupLink : TastesConfiguration.feedLink)
        .privacySensitive()
    }
    private var photoView: some View {
        GeometryReader { geometry in
            if let photo {
                Image(uiImage: photo).resizable().scaledToFill().frame(width: geometry.size.width, height: geometry.size.height).clipped()
            } else {
                background.overlay(Image(systemName: "fork.knife").font(.largeTitle).foregroundStyle(.brown))
            }
        }
    }
    private var footer: some View {
        Text(entry.offline ? "Сохранённая публикация" : "Different Tastes").font(.caption2).foregroundStyle(.secondary)
    }
}

@main
struct LatestTasteWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: TastesConfiguration.widgetKind, provider: LatestTasteProvider()) { entry in
            LatestTasteView(entry: entry)
        }
        .configurationDisplayName("Different Tastes")
        .description("Последняя публикация друзей: фото, оценка и отзыв. Нажми, чтобы открыть сайт.")
        .supportedFamilies([.systemSmall, .systemMedium])
        .contentMarginsDisabled()
    }
}
