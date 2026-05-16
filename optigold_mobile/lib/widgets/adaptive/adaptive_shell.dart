import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/colors.dart';

class AdaptiveShell extends StatelessWidget {
  final Widget child;
  const AdaptiveShell({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return Platform.isIOS
        ? _IOSShell(child: child)
        : _AndroidShell(child: child);
  }
}

// ── iOS: Scaffold + CupertinoTabBar ────────────────────────
// CupertinoTabScaffold is intentionally NOT used here:
// it creates per-tab navigators that conflict with go_router's ShellRoute.
class _IOSShell extends StatefulWidget {
  final Widget child;
  const _IOSShell({required this.child});

  @override
  State<_IOSShell> createState() => _IOSShellState();
}

class _IOSShellState extends State<_IOSShell> {
  int _index = 0;

  static const _routes = ['/home', '/history', '/positions', '/settings'];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: widget.child,
      bottomNavigationBar: CupertinoTabBar(
        currentIndex: _index,
        onTap: (i) {
          setState(() => _index = i);
          context.go(_routes[i]);
        },
        backgroundColor: AppColors.surface,
        activeColor: AppColors.primary,
        inactiveColor: AppColors.textMuted,
        items: const [
          BottomNavigationBarItem(icon: Icon(CupertinoIcons.bolt_fill), label: 'Signal'),
          BottomNavigationBarItem(icon: Icon(CupertinoIcons.clock_fill), label: 'History'),
          BottomNavigationBarItem(icon: Icon(CupertinoIcons.briefcase_fill), label: 'Positions'),
          BottomNavigationBarItem(icon: Icon(CupertinoIcons.settings), label: 'Settings'),
        ],
      ),
    );
  }
}

// ── Android: NavigationBar (Material 3) ────────────────────
class _AndroidShell extends StatefulWidget {
  final Widget child;
  const _AndroidShell({required this.child});

  @override
  State<_AndroidShell> createState() => _AndroidShellState();
}

class _AndroidShellState extends State<_AndroidShell> {
  int _index = 0;

  static const _routes = ['/home', '/history', '/positions', '/settings'];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: widget.child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) {
          setState(() => _index = i);
          context.go(_routes[i]);
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.bolt_outlined),
            selectedIcon: Icon(Icons.bolt),
            label: 'Signal',
          ),
          NavigationDestination(
            icon: Icon(Icons.history_outlined),
            selectedIcon: Icon(Icons.history),
            label: 'History',
          ),
          NavigationDestination(
            icon: Icon(Icons.work_outline_rounded),
            selectedIcon: Icon(Icons.work_rounded),
            label: 'Positions',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}
