# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta

from odoo import api, models

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    @api.model
    def _cron_auto_close_idle_sessions(self):
        """
        Cron job to automatically close POS sessions that have been idle
        for longer than the configured timeout.

        This method:
        1. Gets the idle timeout from configuration
        2. Finds all open sessions for Karage POS configs
        3. Checks each session's last order time
        4. Closes sessions that exceed the idle timeout
        """
        config_param = self.env["ir.config_parameter"].sudo()

        # Check if auto-close is enabled
        auto_close_enabled = config_param.get_param(
            "karage_pos.auto_close_sessions", "True"
        ).lower() == "true"

        if not auto_close_enabled:
            _logger.info("Auto-close sessions is disabled. Skipping.")
            return

        # Get idle timeout in minutes (default: 60)
        try:
            idle_timeout_minutes = int(config_param.get_param(
                "karage_pos.session_idle_timeout_minutes", "60"
            ))
        except (ValueError, TypeError):
            idle_timeout_minutes = 60

        if idle_timeout_minutes <= 0:
            _logger.info("Session idle timeout is 0 or negative. Skipping auto-close.")
            return

        cutoff_time = datetime.now() - timedelta(minutes=idle_timeout_minutes)

        # Get the configured Karage POS config ID
        karage_pos_config_id = config_param.get_param(
            "karage_pos.external_pos_config_id", "0"
        )
        try:
            karage_pos_config_id = int(karage_pos_config_id)
        except (ValueError, TypeError):
            karage_pos_config_id = 0

        if not karage_pos_config_id:
            _logger.warning("No Karage POS config configured. Skipping auto-close.")
            return

        # Find open sessions for the Karage POS config
        open_sessions = self.sudo().search([
            ("config_id", "=", karage_pos_config_id),
            ("state", "in", ["opened", "opening_control"]),
        ])

        _logger.info(
            "Checking %d open Karage POS sessions for idle timeout (cutoff: %s)",
            len(open_sessions), cutoff_time
        )

        closed_count = 0
        for session in open_sessions:
            try:
                if self._should_close_session(session, cutoff_time):
                    if self._auto_close_session(session):
                        closed_count += 1
            except Exception as e:
                _logger.error(
                    "Error auto-closing session %s: %s",
                    session.name, str(e),
                    exc_info=True
                )

        _logger.info("Auto-closed %d idle Karage POS sessions", closed_count)
        return closed_count

    def _should_close_session(self, session, cutoff_time):
        """
        Determine if a session should be auto-closed based on idle time.

        :param session: pos.session record
        :param cutoff_time: datetime threshold - sessions idle before this should close
        :return: True if session should be closed, False otherwise
        """
        # Get the last order time for this session
        last_order = self.env["pos.order"].sudo().search([
            ("session_id", "=", session.id),
            ("state", "!=", "cancel"),
        ], order="create_date desc", limit=1)

        if last_order:
            last_activity_time = last_order.create_date
        else:
            # No orders in session - use session start time
            last_activity_time = session.start_at or session.create_date

        # Check if session has been idle longer than the timeout
        if last_activity_time and last_activity_time < cutoff_time:
            _logger.info(
                "Session %s is idle (last activity: %s, cutoff: %s)",
                session.name, last_activity_time, cutoff_time
            )
            return True

        return False

    def _auto_close_session(self, session):
        """
        Automatically close an idle POS session.

        This method handles the session closing process, including:
        - Checking for draft orders
        - Closing the session gracefully
        - Handling any errors

        :param session: pos.session record to close
        :return: True if closed successfully, False otherwise
        """
        _logger.info("Auto-closing idle session: %s", session.name)

        # Check for draft orders - these would block closing
        draft_orders = session.order_ids.filtered(lambda o: o.state == "draft")
        if draft_orders:
            _logger.warning(
                "Cannot auto-close session %s: %d draft orders exist. Orders: %s",
                session.name,
                len(draft_orders),
                ", ".join(draft_orders.mapped("name"))
            )
            return False

        try:
            # Use Odoo's standard session closing flow
            # First, set session to closing_control state
            if session.state == "opened":
                session.action_pos_session_closing_control()

            # Then close the session
            session.action_pos_session_close()

            _logger.info("Successfully auto-closed session: %s", session.name)
            return True

        except Exception as e:
            _logger.warning(
                "Could not auto-close session %s: %s",
                session.name, str(e)
            )
            return False
