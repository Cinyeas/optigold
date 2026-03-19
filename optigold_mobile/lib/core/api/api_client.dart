import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/constants.dart';
import 'models/signal.dart';
import 'models/market_snapshot.dart';
import 'models/user_profile.dart';
import 'models/position.dart';

class ApiClient {
  late final Dio _dio;

  ApiClient({String? baseUrl}) {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl ?? AppConstants.defaultBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 20),
      headers: {'Content-Type': 'application/json'},
    ));
    _dio.interceptors.add(LogInterceptor(
      requestBody: false,
      responseBody: false,
      error: true,
    ));
  }

  static Future<ApiClient> create() async {
    final prefs = await SharedPreferences.getInstance();
    final url   = prefs.getString(AppConstants.baseUrlKey) ?? AppConstants.defaultBaseUrl;
    return ApiClient(baseUrl: url);
  }

  void updateBaseUrl(String url) {
    _dio.options.baseUrl = url;
  }

  // ── Signals ────────────────────────────────────────────────
  Future<SignalModel> getLatestSignal() async {
    final res = await _dio.get(AppConstants.signalLatest);
    return SignalModel.fromJson(res.data as Map<String, dynamic>);
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
    return MarketSnapshot.fromJson(res.data as Map<String, dynamic>);
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
