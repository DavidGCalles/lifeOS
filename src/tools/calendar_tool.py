from datetime import datetime, timedelta
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from src.tools.google_base import GoogleServiceFactory
from src.identity_manager import UserContext, IdentityManager
import asyncio
from googleapiclient.errors import HttpError
import pytz
from src.logging_config import get_logger
from src.utils.telegram_notifier import TelegramNotifier
import uuid

logger = get_logger(__name__) 

class CalendarListInput(BaseModel):
    days_ahead: int = Field(7, description="How many days into the future to scan. Default is 7.")
    max_results: int = Field(10, description="Maximum number of events to list. Default is 10.")

class CalendarListTool(BaseTool):
    name: str = "CalendarListTool"
    description: str = (
        "Retrieve upcoming events from the user's primary Google Calendar. "
        "Automatically uses the email linked to the user's profile. "
        "Returns a list of events or an error if the email is missing."
    )
    args_schema: type[BaseModel] = CalendarListInput
    
    # Contexto del usuario (Inyectado en runtime)
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        """Inyecta el usuario actual para obtener su calendar_id."""
        self._current_user = user

    def _run(self, days_ahead: int = 7, max_results: int = 10) -> str:
        # 1. Validación (igual)
        if not self._current_user or not self._current_user.calendar_id:
             logger.warning("CalendarListTool invoked without calendar configured for user: %s", getattr(self._current_user, 'telegram_id', 'Unknown'))
             return "❌ Error: User email not configured. Ask the user for it."

        calendar_id = self._current_user.calendar_id
        
        try:
            service = GoogleServiceFactory.build_service('calendar', 'v3')

            # --- TIME LOGIC: Start of Day -> End of Target Day ---
            tz = pytz.timezone('Europe/Madrid')
            now_madrid = datetime.now(tz)
            
            # Inicio del día (00:00:00)
            start_of_day_madrid = now_madrid.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # CORRECCIÓN: Time Max ahora parte del INICIO del día, no de 'now'.
            # Si days_ahead=0, sumamos 1 día para cubrir hasta las 00:00 de mañana.
            # Si days_ahead=7, cubrimos hoy + 7 días completos.
            end_of_target_day = start_of_day_madrid + timedelta(days=days_ahead + 1)
            
            time_min = start_of_day_madrid.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
            time_max = end_of_target_day.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
            # -------------------------------------------------------------------

            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            if not events:
                logger.info("CalendarListTool: no events for calendar %s in next %s days", calendar_id, days_ahead)
                return f"📅 Agenda for {calendar_id}: No upcoming events found for the next {days_ahead} days."

            # 5. Formateo de Salida
            output = [f"📅 Agenda for {calendar_id} (Next {days_ahead} days):"]
                
            for event in events:
                # Extraemos solo lo útil
                start = event['start'].get('dateTime', event['start'].get('date'))
                summary = event.get('summary', '(No Title)')
                
                # Formateo de fecha amigable
                start_str = start
                if 'T' in start:
                    try:
                        dt_obj = datetime.fromisoformat(start)
                        # Formato: "Lun 26, 10:30"
                        start_str = dt_obj.strftime("%a %d, %H:%M") 
                    except:
                        pass
                
                # Agregamos línea limpia
                output.append(f"- {start_str}: {summary}")

            # IMPORTANTE: Devolvemos UN SOLO STRING unido por saltos de línea
            return "\n".join(output)

        except Exception as e:
            logger.exception("CalendarListTool error for calendar %s", getattr(self._current_user, 'telegram_id', 'Unknown'))
            error_msg = str(e)
            if "Not Found" in error_msg:
                return (
                    f"❌ Error: The calendar for '{calendar_id}' was not found or is not accessible. "
                    "Make sure the user has SHARED their calendar with the Service Account email."
                )
            return f"❌ Google API Error: {error_msg}"
        
# --- INPUT SCHEMA PARA ESCRITURA ---
class CalendarAddInput(BaseModel):
    summary: str = Field(..., description="Title of the event (e.g., 'Dentist Appointment').")
    start_time: str = Field(..., description="Start time in format 'YYYY-MM-DD HH:MM' (24h). Example: '2025-10-25 14:30'.")
    duration_minutes: int = Field(60, description="Duration in minutes. Default is 60.")
    description: str = Field("", description="Optional details or description for the event.")
    attendee_emails: list[str] = Field(default_factory=list, description="Optional list of email addresses of attendees to invite.")

# --- HERRAMIENTA DE ESCRITURA ---
class CalendarAddTool(BaseTool):
    name: str = "CalendarAddTool"
    description: str = (
        "Use this tool to SCHEDULE new events in the user's Calendar. "
        "REQUIRES the user to have a configured Google Email. "
        "Input date must be 'YYYY-MM-DD HH:MM'. The timezone is fixed to Europe/Madrid."
    )
    args_schema: type[BaseModel] = CalendarAddInput
    
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        self._current_user = user

    def _run(self, summary: str, start_time: str, duration_minutes: int = 60, description: str = "", attendee_emails: list[str] = None) -> str:
        logger.debug(f"📋 START: {summary}")
        
        # 1. Owner resolution: try ToolContext accessor first, fallback to injected context
        owner = None
        # Preferred: context.get_current_user() if available on BaseTool
        try:
            ctx = getattr(self, 'context', None)
            if ctx and hasattr(ctx, 'get_current_user'):
                owner = ctx.get_current_user()
                logger.debug(f"✓ Owner resolved from ToolContext: {getattr(owner, 'calendar_id', 'N/A')}")
        except Exception as e:
            logger.debug(f"⚠️ ToolContext not available: {e}")
            owner = None

        # Fallback to injected user via set_context
        if not owner:
            owner = self._current_user
            logger.debug(f"✓ Owner resolved from injected context: {getattr(owner, 'calendar_id', 'N/A') if owner else 'None'}")

        if not owner or not getattr(owner, 'calendar_id', None):
            logger.error(f"❌ [CalendarAddTool] FAIL: No owner calendar_id. Owner={owner}, calendar_id={getattr(owner, 'calendar_id', None) if owner else 'N/A'}")
            return "❌ Error: User email not configured. Use 'SetCalendarIDTool' first."

        calendar_id = owner.calendar_id
        tz = pytz.timezone('Europe/Madrid')

        try:
            # 2. Parseo de Fechas (Asumiendo Input Local Madrid)
            try:
                dt_naive = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
                dt_start = tz.localize(dt_naive)
            except ValueError as ve:
                logger.error(f"❌ Date parsing failed: {ve}")
                return "❌ Error: Invalid date format. Please use 'YYYY-MM-DD HH:MM'."

            dt_end = dt_start + timedelta(minutes=duration_minutes)
            service = GoogleServiceFactory.build_service('calendar', 'v3')

            # Resolve attendees: emails or names -> calendar_id + UserContext mapping
            resolved_attendees: list[str] = []
            attendee_contexts: dict[str, UserContext] = {}  # Map email -> UserContext for Telegram notifications
            unresolved: list[str] = []
            
            if attendee_emails:
                logger.debug(f"👥 Resolving {len(attendee_emails)} attendees")
                for a in attendee_emails:
                    # simple email check
                    if '@' in a and '.' in a:
                        resolved_attendees.append(a)
                        try:
                            user = asyncio.run(IdentityManager.get_user_by_email(a))
                            if user:
                                attendee_contexts[a] = user
                                logger.debug(f"  ✓ {a}")
                            else:
                                logger.debug(f"  ⚠️ {a} not found")
                        except Exception:
                            logger.debug(f"  ⚠️ Error resolving {a}")
                    else:
                        # try to resolve by name using IdentityManager (async)
                        try:
                            user = asyncio.run(IdentityManager.get_user_by_name(a))
                            if user and user.calendar_id:
                                resolved_attendees.append(user.calendar_id)
                                attendee_contexts[user.calendar_id] = user
                                logger.debug(f"  ✓ {a}")
                            else:
                                unresolved.append(a)
                        except Exception:
                            unresolved.append(a)
            else:
                logger.info(f"ℹ️ [CalendarAddTool] No attendees specified")

            # Build the list of targets (owner + resolved attendees)
            target_list = [calendar_id] + [e for e in resolved_attendees if e != calendar_id]

            successes: list[str] = []
            failures: list[str] = []

            # Prepare a textual attendees block to include in description (fallback)
            attendees_block = "\nExpected attendees:\n" + "\n".join([f"- {e}" for e in resolved_attendees]) if resolved_attendees else ""

            # Iterate and insert into each target calendar. Do not include attendees field to avoid sending invites.
            for target in target_list:
                event_body = {
                    'summary': summary,
                    'description': (description or "") + attendees_block,
                    'start': {'dateTime': dt_start.isoformat(), 'timeZone': 'Europe/Madrid'},
                    'end': {'dateTime': dt_end.isoformat(), 'timeZone': 'Europe/Madrid'},
                    'attendees': [],
                    'status': 'confirmed',
                    'iCalUID': str(uuid.uuid4()),
                }

                # Optionally set organizer metadata when writing to the owner's calendar
                if target == calendar_id:
                    try:
                        event_body['organizer'] = {'email': calendar_id, 'displayName': owner.name}
                    except Exception:
                        pass

                try:
                    created = service.events().insert(calendarId=target, body=event_body).execute()
                    successes.append(target)
                    logger.debug(f"  ✓ {target}")
                except HttpError as he:
                    logger.debug(f"  ⚠️ {target}: HTTP {he.resp.status}")
                    failures.append(target)
                except Exception as e:
                    logger.debug(f"  ⚠️ {target}: {type(e).__name__}")
                    failures.append(target)

            # Build summary
            ok_list = ", ".join(successes) if successes else "None"
            fail_list = ", ".join(failures) if failures else "None"

            summary_msg = f"✅ Created in: [{ok_list}]\n⚠️ Not accessible: [{fail_list}]"
            if unresolved:
                summary_msg += f"\n❓ Could not resolve names: {', '.join(unresolved)}"

            # Send Telegram notifications to all attendees (both successful and failed writes)
            # They should know about the event even if the system couldn't write to their calendar
            logger.info(f"📱 [CalendarAddTool] Sending Telegram notifications to {len(attendee_contexts)} attendees...")
            start_time_display = dt_start.strftime("%a, %b %d at %H:%M")
            notification_desc = description[:100] + "..." if description and len(description) > 100 else (description or "")

            for email, attendee_user in attendee_contexts.items():
                if attendee_user.telegram_id:
                    try:
                        asyncio.run(
                            TelegramNotifier.send_event_notification(
                                telegram_id=attendee_user.telegram_id,
                                event_summary=summary,
                                start_time=start_time_display,
                                description=notification_desc,
                                organizer_name=owner.name,
                            )
                        )
                    except Exception:
                        logger.debug(f"  ⚠️ Telegram notification failed")

            logger.info(f"✅ Event created: {summary}")
            return summary_msg

        except Exception as e:
            logger.exception(f"❌ [CalendarAddTool] FATAL ERROR for user {getattr(owner, 'telegram_id', 'Unknown')}: {type(e).__name__}: {e}")
            return f"❌ Google API Error: {str(e)}"

# --- INPUT SCHEMA PARA BORRADO ---
class CalendarDeleteInput(BaseModel):
    query: str = Field(..., description="Text to search for matching event to delete (e.g., 'Dentist'). Be specific.")

# --- HERRAMIENTA DE BORRADO ---
class CalendarDeleteTool(BaseTool):
    name: str = "CalendarDeleteTool"
    description: str = (
        "Use this tool to DELETE an existing event from the user's Calendar. "
        "It searches for upcoming events (next 30 days) matching the query. "
        "SAFETY: If multiple events match, it will fail and ask for clarification to avoid accidents."
    )
    args_schema: type[BaseModel] = CalendarDeleteInput
    
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        self._current_user = user

    def _run(self, query: str) -> str:
        # 1. Validación de Identidad
        if not self._current_user or not self._current_user.calendar_id:
            logger.warning("CalendarDeleteTool invoked without calendar configured for user: %s", getattr(self._current_user, 'telegram_id', 'Unknown'))
            return "❌ Error: User email not configured. Cannot access calendar."

        calendar_id = self._current_user.calendar_id
        
        try:
            logger.info("CalendarDeleteTool: searching for '%s' in calendar %s", query, calendar_id)
            service = GoogleServiceFactory.build_service('calendar', 'v3')
            
            # 2. Definir rango de búsqueda (Próximos 30 días)
            tz = pytz.timezone('Europe/Madrid')
            now_madrid = datetime.now(tz)
            
            time_min = now_madrid.isoformat()
            # 30 días de ventana de seguridad
            time_max = (now_madrid + timedelta(days=30)).isoformat()

            # 3. Buscar eventos candidatos (Query 'q' filtra por texto libre en title/description)
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                q=query, 
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            # 4. Lógica de Seguridad (Ambiguity Check)
            if not events:
                logger.info("CalendarDeleteTool: no matches for '%s' in calendar %s", query, calendar_id)
                return f"⚠️ No matching events found for '{query}' in the next 30 days."

            if len(events) > 1:
                logger.warning("CalendarDeleteTool: ambiguity - %d matches for '%s' in calendar %s", len(events), query, calendar_id)
                # Conflicto: Devolvemos lista para que el Agente pida clarificación
                conflict_list = []
                for e in events:
                    start = e['start'].get('dateTime', e['start'].get('date'))
                    summary = e.get('summary', '(No Title)')
                    conflict_list.append(f"- {summary} at {start}")
                
                return (
                    f"🛑 AMBIGUITY ERROR: Found {len(events)} events matching '{query}'. "
                    "I will not delete anything to be safe. Please refine your query.\n"
                    f"Matches found:\n" + "\n".join(conflict_list)
                )

            # 5. Ejecución (Solo si hay EXACTAMENTE 1 coincidencia)
            target_event = events[0]
            event_id = target_event['id']
            event_summary = target_event.get('summary', 'Unknown')
            event_time = target_event['start'].get('dateTime', 'Unknown')

            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()

            logger.info("CalendarDeleteTool: deleted event id=%s summary=%s", event_id, event_summary)
            return f"🗑️ DELETED: '{event_summary}' at {event_time}."

        except Exception as e:
            logger.exception("CalendarDeleteTool failed for calendar %s with query=%s", calendar_id, query)
            return f"❌ Error deleting event: {str(e)}"
        
# --- INPUT SCHEMA PARA UPDATE ---
class CalendarUpdateInput(BaseModel):
    query: str = Field(..., description="Search query to identify the unique event to update (e.g., 'Dentist').")
    new_summary: str | None = Field(None, description="New title for the event.")
    new_start_time: str | None = Field(None, description="New start time 'YYYY-MM-DD HH:MM'. Timezone is Europe/Madrid.")
    new_duration: int | None = Field(None, description="New duration in minutes.")
    new_description: str | None = Field(None, description="New description text.")

class CalendarUpdateTool(BaseTool):
    name: str = "CalendarUpdateTool"
    description: str = (
        "Use this tool to MODIFY an existing event. "
        "First, it searches for the event. If found unique, it updates ONLY the provided fields. "
        "Useful for rescheduling or renaming events."
    )
    args_schema: type[BaseModel] = CalendarUpdateInput
    
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        self._current_user = user

    def _run(self, query: str, new_summary: str = None, new_start_time: str = None, new_duration: int = None, new_description: str = None) -> str:
        if not self._current_user or not self._current_user.calendar_id:
            logger.warning("CalendarUpdateTool invoked without calendar configured for user: %s", getattr(self._current_user, 'telegram_id', 'Unknown'))
            return "❌ Error: User email not configured."

        calendar_id = self._current_user.calendar_id
        
        try:
            logger.info("CalendarUpdateTool: searching updates for query=%s in calendar=%s", query, calendar_id)
            service = GoogleServiceFactory.build_service('calendar', 'v3')
            tz = pytz.timezone('Europe/Madrid')
            
            # 1. BÚSQUEDA (Ventana de 30 días)
            now = datetime.now(tz)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=30)).isoformat()

            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                q=query,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            # 2. GESTIÓN DE AMBIGÜEDAD
            if not events:
                logger.info("CalendarUpdateTool: no events matching %s in calendar %s", query, calendar_id)
                return f"⚠️ No events found matching '{query}' to update."
            
            if len(events) > 1:
                logger.warning("CalendarUpdateTool: ambiguity - %d matches for %s in calendar %s", len(events), query, calendar_id)
                conflict_list = [f"- {e.get('summary')} at {e['start'].get('dateTime')}" for e in events]
                return (
                    f"🛑 AMBIGUITY: Found {len(events)} matches. Please be more specific.\n" + 
                    "\n".join(conflict_list)
                )

            # 3. PREPARAR EL PATCH
            target_event = events[0]
            event_id = target_event['id']
            changes = {}

            if new_summary:
                changes['summary'] = new_summary
            
            if new_description:
                changes['description'] = new_description

            if new_start_time:
                # Recalcular start/end completo
                try:
                    dt_naive = datetime.strptime(new_start_time, "%Y-%m-%d %H:%M")
                    dt_start = tz.localize(dt_naive)
                    
                    # Si no pasan nueva duración, calculamos la antigua
                    if new_duration:
                        duration = new_duration
                    else:
                        orig_start = datetime.fromisoformat(target_event['start']['dateTime'])
                        orig_end = datetime.fromisoformat(target_event['end']['dateTime'])
                        duration = (orig_end - orig_start).seconds // 60

                    dt_end = dt_start + timedelta(minutes=duration)

                    changes['start'] = {'dateTime': dt_start.isoformat(), 'timeZone': 'Europe/Madrid'}
                    changes['end'] = {'dateTime': dt_end.isoformat(), 'timeZone': 'Europe/Madrid'}
                
                except ValueError:
                    return "❌ Error: Invalid date format. Use 'YYYY-MM-DD HH:MM'."

            elif new_duration:
                # Solo cambia duración, mantenemos start original
                orig_start = datetime.fromisoformat(target_event['start']['dateTime'])
                dt_end = orig_start + timedelta(minutes=new_duration)
                changes['end'] = {'dateTime': dt_end.isoformat(), 'timeZone': 'Europe/Madrid'}

            if not changes:
                return "⚠️ No changes requested. Provide at least one new value."

            # 4. EJECUTAR UPDATE
            updated_event = service.events().patch(
                calendarId=calendar_id,
                eventId=event_id,
                body=changes
            ).execute()

            # Extraemos la hora actualizada para confirmar
            final_start = updated_event.get('start', {}).get('dateTime', 'Unknown')
            logger.info("CalendarUpdateTool: updated event id=%s with changes=%s", event_id, changes)
            return f"✅ UPDATED: '{updated_event.get('summary')}' is now at {final_start}."

        except Exception as e:
            logger.exception("CalendarUpdateTool failed for calendar %s with query=%s", calendar_id, query)
            return f"❌ Update Failed: {str(e)}"