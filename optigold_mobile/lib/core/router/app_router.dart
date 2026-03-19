import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../screens/onboarding/onboarding_screen.dart';
import '../../screens/home/home_screen.dart';
import '../../screens/signal_detail/signal_detail_screen.dart';
import '../../screens/history/history_screen.dart';
import '../../screens/positions/positions_screen.dart';
import '../../screens/settings/settings_screen.dart';
import '../../widgets/adaptive/adaptive_shell.dart';
import '../utils/constants.dart';

final _rootNavigatorKey    = GlobalKey<NavigatorState>();
final _shellNavigatorKey   = GlobalKey<NavigatorState>();

GoRouter buildRouter() => GoRouter(
      navigatorKey: _rootNavigatorKey,
      initialLocation: '/home',
      redirect: (context, state) async {
        final prefs  = await SharedPreferences.getInstance();
        final done   = prefs.getBool(AppConstants.onboardedKey) ?? false;
        if (!done && state.matchedLocation != '/onboarding') {
          return '/onboarding';
        }
        return null;
      },
      routes: [
        GoRoute(
          path: '/onboarding',
          builder: (_, __) => const OnboardingScreen(),
        ),
        ShellRoute(
          navigatorKey: _shellNavigatorKey,
          builder: (_, __, child) => AdaptiveShell(child: child),
          routes: [
            GoRoute(
              path: '/home',
              pageBuilder: (_, state) => _fade(const HomeScreen(), state),
            ),
            GoRoute(
              path: '/history',
              pageBuilder: (_, state) => _fade(const HistoryScreen(), state),
            ),
            GoRoute(
              path: '/positions',
              pageBuilder: (_, state) => _fade(const PositionsScreen(), state),
            ),
            GoRoute(
              path: '/settings',
              pageBuilder: (_, state) => _fade(const SettingsScreen(), state),
            ),
          ],
        ),
        GoRoute(
          path: '/signal/:id',
          parentNavigatorKey: _rootNavigatorKey,
          builder: (_, state) => SignalDetailScreen(
            signalId: state.pathParameters['id']!,
          ),
        ),
      ],
    );

CustomTransitionPage<void> _fade(Widget child, GoRouterState state) =>
    CustomTransitionPage<void>(
      key: state.pageKey,
      child: child,
      transitionsBuilder: (_, animation, __, c) =>
          FadeTransition(opacity: animation, child: c),
      transitionDuration: const Duration(milliseconds: 200),
    );
