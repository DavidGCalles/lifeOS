from datetime import datetime, timedelta
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from src.tools.google_base import GoogleServiceFactory
from src.identity_manager import UserContext
import pytz

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
        # 1. Validación de Identidad
        if not self._current_user:
            return "❌ Error: System Error. User context is missing."
        
        if not self._current_user.calendar_id:
            # Esta respuesta instruye al Agente para que pida el email
            return (
                "❌ Error: I don't have a Google Calendar email linked to this user yet. "
                "Action Required: Ask the user for their Google email address and use "
                "'SetCalendarIDTool' to save it."
            )

        calendar_id = self._current_user.calendar_id

        try:
            # 2. Construcción del Servicio
            service = GoogleServiceFactory.build_service('calendar', 'v3')

            # 3. Cálculo de fechas (UTC)
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=days_ahead)).isoformat() + 'Z'

            # 4. Llamada a Google API
            # print(f"📅 Reading Calendar for: {calendar_id}") # Log opcional
            
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
                return f"📅 Agenda for {calendar_id}: No upcoming events found for the next {days_ahead} days."

            # 5. Formateo de Salida
            output = [f"📅 Agenda for {calendar_id} (Next {days_ahead} days):"]
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                summary = event.get('summary', '(No Title)')
                
                # Limpieza de fecha
                if 'T' in start:
                    dt_obj = datetime.fromisoformat(start)
                    # Formato amigable: "Lunes, 20 Ene 10:00"
                    start_str = dt_obj.strftime("%a, %d %b %H:%M")
                else:
                    start_str = f"{start} (All Day)"

                output.append(f"- [{start_str}] {summary}")

            return "\n".join(output)

        except Exception as e:
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

    def _run(self, summary: str, start_time: str, duration_minutes: int = 60, description: str = "") -> str:
        # 1. Validación de Identidad
        if not self._current_user or not self._current_user.calendar_id:
            return "❌ Error: User email not configured. Use 'SetCalendarIDTool' first."

        calendar_id = self._current_user.calendar_id
        tz = pytz.timezone('Europe/Madrid')

        try:
            # 2. Parseo de Fechas (Asumiendo Input Local Madrid)
            # El agente te pasará "2026-01-27 10:00". Nosotros le decimos a Python: "Esto es Madrid".
            try:
                dt_naive = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
                dt_start = tz.localize(dt_naive)
            except ValueError:
                return "❌ Error: Invalid date format. Please use 'YYYY-MM-DD HH:MM'."

            dt_end = dt_start + timedelta(minutes=duration_minutes)

            # 3. Construcción del Payload
            event_body = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': dt_start.isoformat(),
                    'timeZone': 'Europe/Madrid',
                },
                'end': {
                    'dateTime': dt_end.isoformat(),
                    'timeZone': 'Europe/Madrid',
                },
            }

            # 4. Llamada a la API
            service = GoogleServiceFactory.build_service('calendar', 'v3')
            event = service.events().insert(calendarId=calendar_id, body=event_body).execute()

            # 5. Confirmación
            html_link = event.get('htmlLink', '#')
            return f"✅ Event Scheduled: '{summary}' on {start_time} ({duration_minutes} min).\nLink: {html_link}"

        except Exception as e:
            return f"❌ Error scheduling event: {str(e)}"