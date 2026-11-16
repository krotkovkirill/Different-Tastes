import SwiftUI
import WidgetKit
import UIKit

@MainActor
final class ConnectionModel: ObservableObject {
    @Published var code = ""
    @Published var connected = false
    @Published var busy = false
    @Published var message: String?
    @Published var feed: LatestFeed?

    func load() async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            guard let saved = try SharedConnection.read() else { return }
            connected = true
            feed = SharedFeedCache.read(code: saved)
            let fresh = try await LatestFeedAPI.fetch(code: saved)
            feed = fresh
            try? SharedFeedCache.save(fresh, code: saved)
            WidgetCenter.shared.reloadTimelines(ofKind: TastesConfiguration.widgetKind)
        } catch ConnectionError.unauthorized {
            disconnect()
            message = "Подключение истекло или отключено. Создай новый код в профиле сайта."
        } catch {
            message = "Сейчас не удалось обновить публикацию. Попробуй ещё раз."
        }
    }
    func connect() async {
        guard !busy else { return }
        busy = true
        message = nil
        defer { busy = false }
        do {
            let value = code.trimmingCharacters(in: .whitespacesAndNewlines)
            let fresh = try await LatestFeedAPI.fetch(code: value)
            try SharedConnection.save(value)
            try? SharedFeedCache.save(fresh, code: value)
            connected = true
            feed = fresh
            code = ""
            message = "Подключено. Теперь добавь виджет Different Tastes на главный экран."
            WidgetCenter.shared.reloadTimelines(ofKind: TastesConfiguration.widgetKind)
        } catch ConnectionError.invalidCode {
            message = "Вставь полный код подключения из профиля сайта."
        } catch ConnectionError.unauthorized {
            message = "Код неверный или отключён. Создай новый код на сайте."
        } catch ConnectionError.storage(_) {
            message = "Не удалось сохранить подключение на устройстве."
        } catch {
            message = "Не удалось подключиться. Проверь интернет и попробуй ещё раз."
        }
    }
    func disconnect() {
        do {
            try SharedConnection.remove()
            SharedFeedCache.remove()
            connected = false
            feed = nil
            WidgetCenter.shared.reloadTimelines(ofKind: TastesConfiguration.widgetKind)
        } catch {
            message = "Не удалось отключить виджет на устройстве. Попробуй ещё раз."
        }
    }
}

@main
struct DifferentTastesApp: App {
    var body: some Scene {
        WindowGroup {
            ConnectionView()
                .onOpenURL { url in
                    if url.scheme == "differenttastes", url.host == "feed" {
                        UIApplication.shared.open(TastesConfiguration.siteURL)
                    }
                }
        }
    }
}

struct ConnectionView: View {
    @StateObject private var model = ConnectionModel()
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Label("Вкусы друзей — на главном экране", systemImage: "square.grid.2x2.fill")
                        .font(.title2.bold())
                    Text("Основное приложение работает на сайте. Здесь подключается виджет последней публикации твоей ленты.")
                        .foregroundStyle(.secondary)
                    Link(destination: TastesConfiguration.siteURL) {
                        Label("Открыть всю ленту", systemImage: "arrow.up.right.square")
                            .frame(maxWidth: .infinity).padding(.vertical, 8)
                    }.buttonStyle(.borderedProminent)
                    if let post = model.feed?.post {
                        if let data = post.imageData, let photo = UIImage(data: data) {
                            Image(uiImage: photo).resizable().scaledToFit().frame(maxHeight: 230).clipShape(RoundedRectangle(cornerRadius: 20))
                        }
                        Text(post.username).font(.headline)
                        Label("\(post.rating) / 5", systemImage: "star.fill").foregroundStyle(.orange)
                        if !post.comment.isEmpty { Text(post.comment) }
                    } else if model.connected {
                        Text("В ленте пока нет публикаций.").foregroundStyle(.secondary)
                    }
                    if !model.connected {
                        Text("1. Открой профиль на сайте → «Виджет iPhone» → «Создать код».")
                        Text("2. Вставь код подключения сюда.")
                        SecureField("Код подключения", text: $model.code)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                            .textFieldStyle(.roundedBorder)
                            .onSubmit { Task { await model.connect() } }
                        Button("Подключить виджет") { Task { await model.connect() } }
                            .buttonStyle(.borderedProminent).disabled(model.code.isEmpty || model.busy)
                    } else {
                        Text("Подключено").font(.headline).foregroundStyle(.green)
                        Button("Обновить публикацию") { Task { await model.load() } }.buttonStyle(.bordered)
                        Button("Отключить на этом устройстве", role: .destructive) { model.disconnect() }
                    }
                    if model.busy { ProgressView() }
                    if let message = model.message { Text(message).foregroundStyle(.secondary) }
                    Divider()
                    Text("Как добавить виджет").font(.headline)
                    Text("Удерживай свободное место на главном экране iPhone, открой добавление виджетов и выбери Different Tastes. Доступны маленький и средний размеры.")
                    Text("Частоту фонового обновления определяет iOS. Нажатие на виджет откроет сайт со всей лентой.")
                        .font(.footnote).foregroundStyle(.secondary)
                }.padding(24).disabled(model.busy)
            }
            .navigationTitle("Different Tastes")
            .task { await model.load() }
        }.tint(Color(red: 0.48, green: 0.36, blue: 0.05))
    }
}
