#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2016 Adrian Perez <aperez@igalia.com>
#
# Distributed under terms of the GPLv3 license.

from gi.repository import Gtk, Gdk, Gio, WebKit2, GObject


class MainWindow(Gtk.ApplicationWindow):
    network_busy = GObject.Property(type=bool, default=False)

    def __init__(self, application, saved_state):
        self.application = application
        self.saved_state = saved_state
        Gtk.ApplicationWindow.__init__(self,
                                       application=application,
                                       role="main-window",
                                       default_width=saved_state.get_uint("width"),
                                       default_height=saved_state.get_uint("height"),
                                       icon_name=application.get_application_id())
        if self.saved_state.get_boolean("maximized"):
            self.maximize()
        self.saved_state.bind("maximized", self, "is-maximized", Gio.SettingsBindFlags.SET)

        self.set_titlebar(self.__make_headerbar())
        self.set_title(u"Revolt")
        application.add_window(self)
        self._webview = WebKit2.WebView(user_content_manager=self.__create_content_manager(),
                                        web_context=self.__create_web_context())
        self._webview.connect("decide-policy", self.__on_decide_policy)
        application.settings.bind("zoom-factor", self._webview, "zoom-level",
                                  Gio.SettingsBindFlags.GET)
        if hasattr(self._webview, "set_maintains_back_forward_list"):
            self._webview.set_maintains_back_forward_list(False)
        websettings = self._webview.get_settings()
        application.settings.bind("enable-developer-tools", websettings,
                                  "enable-developer-extras",
                                  Gio.SettingsBindFlags.GET)
        application.settings.bind("enable-developer-tools", websettings,
                                  "enable-write-console-messages-to-stdout",
                                  Gio.SettingsBindFlags.GET)
        websettings.set_allow_file_access_from_file_urls(True)
        websettings.set_allow_modal_dialogs(False)  # TODO
        websettings.set_enable_fullscreen(False)
        websettings.set_enable_java(False)
        websettings.set_enable_media_stream(True)
        websettings.set_enable_page_cache(False)  # Single-page app
        websettings.set_enable_plugins(False)
        websettings.set_enable_smooth_scrolling(True)
        websettings.set_enable_webaudio(True)
        websettings.set_javascript_can_access_clipboard(True)
        websettings.set_minimum_font_size(12)  # TODO: Make it a setting
        websettings.set_property("enable-mediasource", True)
        self._webview.show_all()
        self.add(self._webview)
        self.__connect_widgets()
        self.__notification_ids = set()

    def do_configure_event(self, event):
        result = Gtk.ApplicationWindow.do_configure_event(self, event)
        width, height = self.get_size()
        self.saved_state.set_uint("width", width)
        self.saved_state.set_uint("height", height)
        return result

    def __make_headerbar(self):
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        spinner = Gtk.Spinner()
        header.pack_end(spinner)
        self.bind_property("network-busy", spinner, "active",
                           GObject.BindingFlags.DEFAULT)
        header.show_all()
        return header

    def __create_web_context(self):
        ctx = WebKit2.WebContext.get_default()
        ctx.set_web_process_count_limit(1)
        ctx.set_spell_checking_enabled(False)
        ctx.set_tls_errors_policy(WebKit2.TLSErrorsPolicy.FAIL)
        return ctx

    def __create_content_manager(self):
        mgr = WebKit2.UserContentManager()
        script = WebKit2.UserScript("Notification.requestPermission();",
                                    WebKit2.UserContentInjectedFrames.TOP_FRAME,
                                    WebKit2.UserScriptInjectionTime.START,
                                    None, None)
        mgr.add_script(script)
        return mgr

    def __on_decide_policy(self, webview, decision, decision_type):
        if decision_type == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            if decision.get_navigation_type() == WebKit2.NavigationType.LINK_CLICKED:
                uri = decision.get_request().get_uri()
                if not uri.startswith(self.application.riot_url):
                    Gtk.show_uri(uri)
                    return True
        elif decision_type == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
            if decision.get_navigation_type() == WebKit2.NavigationType.LINK_CLICKED:
                Gtk.show_uri(None, decision.get_request().get_uri(), Gdk.CURRENT_TIME)
                return True
        return False

    def __on_has_toplevel_focus_changed(self, window, has_focus):
        assert window == self
        if window.has_toplevel_focus():
            # Clear the window's urgency hint
            window.set_urgency_hint(False)
            # Dismiss notifications
            for notification_id in self.__notification_ids:
                self.application.withdraw_notification(notification_id)
            self.__notification_ids.clear()
            self.application.statusicon.clear_notifications()

    def __on_load_changed(self, webview, event):
        if event == WebKit2.LoadEvent.FINISHED:
            self.network_busy = False
            self.application.statusicon.set_status("connected")
        else:
            self.network_busy = True
            self.application.statusicon.set_status("disconnected")

    def __on_show_notification(self, webview, notification):
        # TODO: Handle notification clicked, and so
        if not self.has_toplevel_focus():
            self.set_urgency_hint(True)
            notif = Gio.Notification.new(notification.get_title())
            notif.set_body(notification.get_body())
            # TODO: Use the avatar of the contact, if available.
            notif.set_icon(Gio.ThemedIcon.new(self.application.get_application_id()))
            notif.set_priority(Gio.NotificationPriority.HIGH)
            # use title as notification id:
            # allows to reuse one notification for the same conversation
            notification_id = notification.get_title()
            self.__notification_ids.add(notification_id)
            self.application.send_notification(notification_id, notif)
            self.application.statusicon.add_notification("%s: %s" % (notification.get_title(),
                                                                     notification.get_body()))
        return True

    def __on_permission_request(self, webview, request):
        if isinstance(request, WebKit2.NotificationPermissionRequest):
            request.allow()
            return True

    def __connect_widgets(self):
        self.connect("notify::has-toplevel-focus", self.__on_has_toplevel_focus_changed)
        self._webview.connect("load-changed", self.__on_load_changed)
        self._webview.connect("show-notification", self.__on_show_notification)
        self._webview.connect("permission-request", self.__on_permission_request)

    def load_riot(self):
        self._webview.load_uri(self.application.riot_url)
        return self

    def load_settings_page(self):
        from urllib.parse import urlsplit, urlunsplit
        url = list(urlsplit(self._webview.get_uri()))
        url[-1] = "#settings"
        self._webview.load_uri(urlunsplit(url))

    def finish(self):
        # TODO: Most likely this can be moved to do_destroy()
        self._webview.stop_loading()
        self.hide()
        self.destroy()
        del self._webview
        return self