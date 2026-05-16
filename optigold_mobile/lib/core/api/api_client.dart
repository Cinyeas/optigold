import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/constants.dart';
import 'models/signal.dart';
import 'models/market_snapshot.dart';
import 'models/user_profile.dart';
import 'models/position.dart';

class ApiClient {
  late final Dio _dio;
  late final SharedPreferences _prefs;

  static const _kSignalCache  = 'cache_v1_latest_signal';
  static const _kMarketCache  = 'cache_v1_market_snapshot';

  ApiClient._({required String baseUrl, required SharedPreferences prefs}) {
    _prefs = prefs;
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 20),
      headers: {'Content-Type': 'application/json'},
    ));
  }

  static Future<ApiClient> create() async {
    final prefs = await SharedPreferences.getInstance();
    final url   = prefs.getString(AppConstants.baseUrlKey) ?? AppConstants.defaultBaseUrl;
    return ApiClient._(baseUrl: url, prefs: prefs);
  }

  /// Synchronous factory — use when SharedPreferences is already loaded.
  static ApiClient createSync(SharedPreferences prefs) {
    final url = prefs.getString(AppConstants.baseUrlKey) ?? AppConstants.defaultBaseUrl;
    return ApiClient._(baseUrl: url, prefs: prefs);
  }

  // ── Cache helpers ───────────────────────────────────────────
  SignalModel? getCachedSignal() {
    final s = _prefs.getString(_kSignalCache);
    if (s == null) return null;
    try { return SignalModel.fromJson(jsonDecode(s) as Map<String, dynamic>); }
    catch (_) { return null; }
  }

  MarketSnapshot? getCachedMarket() {
    final s = _prefs.getString(_kMarketCache);
    if (s == null) return null;
    try { return MarketSnapshot.fromJson(jsonDecode(s) as Map<String, dynamic>); }
    catch (_) { return null; }
  }

  void updateBaseUrl(String url) {
    _dio.options.baseUrl = url;
  }

  // ── Signals ────────────────────────────────────────────────
  Future<SignalModel> getLatestSignal() async {
    final res = await _dio.get(AppConstants.signalLatest);
    final model = SignalModel.fromJson(res.data as Map<String, dynamic>);
    await _prefs.setString(_kSignalCache, jsonEncode(res.data));
    return model;
  }

  Future<SignalModel> refreshSignal() async {
    final res = await _dio.post(AppConstants.signalRefresh);
    return SignalModel.fromJson(res.data as Map<String, dynamic>);
  }

  Future<SignalModel> getSignal(String id) async {
    final res = await _dio.get('${AppConstants.signalList}$id');
    return SignalModel.fromJson(res.data as Map<String, dynamic>);
  }

  Future<({List<SignalListItem> items, int total})> listSignals({
    int page = 1,
    int pageSize = 20,
  }) async {
    final res = await _dio.get(
      AppConstants.signalList,
      queryParameters: {'page': page, 'page_size': pageSize},
    );
    final data = res.data as Map<String, dynamic>;
    final items = (data['items'] as List)
        .map((e) => SignalListItem.fromJson(e as Map<String, dynamic>))
        .toList();
    return (items: items, total: data['total'] as int);
  }

  // ── Market ─────────────────────────────────────────────────
  Future<MarketSnapshot> getMarketSnapshot() async {
    final res = await _dio.get(AppConstants.marketSnapshot);
    final model = MarketSnapshot.fromJson(res.data as Map<String, dynamic>);
    await _prefs.setString(_kMarketCache, jsonEncode(res.data));
    return model;
  }

  // ── Profile ────────────────────────────────────────────────
  Future<UserProfile> getProfile() async {
    final res = await _dio.get(AppConstants.settings);
    return UserProfile.fromJson(res.data as Map<String, dynamic>);
  }

  Future<UserProfile> updateProfile(Map<String, dynamic> updates) async {
    final res = await _dio.put(AppConstants.settings, data: updates);
    return UserProfile.fromJson(res.data as Map<String, dynamic>);
  }

  // ── Positions ──────────────────────────────────────────────
  Future<List<PositionModel>> listPositions({String? status}) async {
    final res = await _dio.get(
      AppConstants.positions,
      queryParameters: status != null ? {'status': status} : null,
    );
    return (res.data as List)
        .map((e) => PositionModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<PositionModel> createPosition(Map<String, dynamic> data) async {
    final res = await _dio.post(AppConstants.positions, data: data);
    return PositionModel.fromJson(res.data as Map<String, dynamic>);
  }

  Future<PositionModel> updatePosition(int id, Map<String, dynamic> data) async {
    final res = await _dio.patch('${AppConstants.positions}$id', data: data);
    return PositionModel.fromJson(res.data as Map<String, dynamic>);
  }

  Future<PositionModel> closePosition(
    int id,
    double closePrice, {
    String? closeReason,
    String? notes,
  }) async {
    final res = await _dio.put(
      '${AppConstants.positions}$id/close',
      data: {
        'close_price': closePrice,
        if (closeReason != null) 'close_reason': closeReason,
        if (notes != null) 'notes': notes,
      },
    );
    return PositionModel.fromJson(res.data as Map<String, dynamic>);
  }

  Future<void> deletePosition(int id) async {
    await _dio.delete('${AppConstants.positions}$id');
  }

  // ── Notifications ──────────────────────────────────────────
  Future<void> registerDeviceToken(String token, String platform) async {
    await _dio.post(AppConstants.notifRegister, data: {
      'token': token,
      'platform': platform,
    });
  }
}
