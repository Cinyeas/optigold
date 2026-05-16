class AppConstants {
  AppConstants._();

  // Android emulator: 10.0.2.2 | iOS real device: Mac LAN IP
  static const String defaultBaseUrl = 'http://192.168.0.10:8000';
  static const String baseUrlKey     = 'api_base_url';
  static const String onboardedKey   = 'onboarding_complete';

  // API paths
  static const String signalLatest   = '/api/v1/signals/latest';
  static const String signalRefresh  = '/api/v1/signals/refresh';
  static const String signalList     = '/api/v1/signals/';
  static const String marketSnapshot = '/api/v1/market/snapshot';
  static const String ivRank         = '/api/v1/market/iv-rank';
  static const String settings       = '/api/v1/settings/';
  static const String positions      = '/api/v1/positions/';
  static const String notifRegister  = '/api/v1/notifications/register';
}
