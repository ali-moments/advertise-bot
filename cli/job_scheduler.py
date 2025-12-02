"""
Job Scheduler Module

This module provides job scheduling functionality for recurring tasks
including scraping operations and message sending. Uses APScheduler for
scheduling and integrates with ConfigManager for persistence.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.job import Job as APJob
from rich.console import Console

from cli.models import JobConfig, Job
from cli.config_manager import ConfigManager
from cli.ui_components import UIComponents

logger = logging.getLogger(__name__)


class JobScheduler:
    """Manages scheduled jobs and recurring tasks"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize job scheduler
        
        Args:
            config_manager: ConfigManager instance for persistence
        """
        self.config_manager = config_manager
        self.jobs: Dict[str, Job] = {}
        self.scheduler = AsyncIOScheduler()
        self.job_handlers: Dict[str, Callable] = {}
        self._running = False
    
    def register_handler(self, job_type: str, handler: Callable):
        """
        Register a handler function for a job type
        
        Args:
            job_type: Type of job (e.g., 'scrape_links', 'scrape_members')
            handler: Async function to execute for this job type
        """
        self.job_handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")
    
    async def create_job(self, job_config: JobConfig) -> str:
        """
        Create a new scheduled job
        
        Args:
            job_config: JobConfig object with job details
            
        Returns:
            Job ID of the created job
            
        Requirements: 5.1, 5.2, 10.1
        """
        # Validate schedule interval (1-168 hours)
        if job_config.schedule_interval < 1 or job_config.schedule_interval > 168:
            raise ValueError("Schedule interval must be between 1 and 168 hours")
        
        # Validate job type
        if job_config.job_type not in self.job_handlers:
            raise ValueError(f"Unknown job type: {job_config.job_type}")
        
        # Create Job object
        job = Job(
            config=job_config,
            last_run=None,
            next_run=None,
            status='pending',
            error=None
        )
        
        # Store in memory
        self.jobs[job_config.job_id] = job
        
        # Persist to configuration
        await self.config_manager.add_job(job_config)
        
        # Schedule the job if enabled and scheduler is running
        if job_config.enabled and self._running:
            await self._schedule_job(job)
        
        logger.info(f"Created job: {job_config.job_id} ({job_config.job_type})")
        return job_config.job_id
    
    async def update_job(self, job_config: JobConfig) -> bool:
        """
        Update an existing job configuration
        
        Args:
            job_config: Updated JobConfig object
            
        Returns:
            True if updated successfully, False otherwise
            
        Requirements: 5.2, 5.4
        """
        if job_config.job_id not in self.jobs:
            logger.warning(f"Job {job_config.job_id} not found for update")
            return False
        
        # Validate schedule interval
        if job_config.schedule_interval < 1 or job_config.schedule_interval > 168:
            raise ValueError("Schedule interval must be between 1 and 168 hours")
        
        # Get existing job
        job = self.jobs[job_config.job_id]
        
        # Remove old scheduled job
        if self._running:
            self._unschedule_job(job_config.job_id)
        
        # Update config
        job.config = job_config
        
        # Persist to configuration
        await self.config_manager.update_job(job_config)
        
        # Reschedule if enabled
        if job_config.enabled and self._running:
            await self._schedule_job(job)
        
        logger.info(f"Updated job: {job_config.job_id}")
        return True
    
    async def delete_job(self, job_id: str) -> bool:
        """
        Delete a scheduled job
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if deleted successfully, False otherwise
            
        Requirements: 5.2, 5.4
        """
        if job_id not in self.jobs:
            logger.warning(f"Job {job_id} not found for deletion")
            return False
        
        # Remove from scheduler
        if self._running:
            self._unschedule_job(job_id)
        
        # Remove from memory
        del self.jobs[job_id]
        
        # Remove from configuration
        await self.config_manager.remove_job(job_id)
        
        logger.info(f"Deleted job: {job_id}")
        return True
    
    async def run_job_now(self, job_id: str):
        """
        Execute a job immediately (outside of schedule)
        
        Args:
            job_id: Job identifier
            
        Requirements: 5.2, 5.5
        """
        if job_id not in self.jobs:
            raise ValueError(f"Job {job_id} not found")
        
        job = self.jobs[job_id]
        
        logger.info(f"Running job immediately: {job_id}")
        await self._execute_job(job)
    
    def list_jobs(self) -> List[Job]:
        """
        Get all scheduled jobs
        
        Returns:
            List of Job objects
            
        Requirements: 5.2, 5.4
        """
        return list(self.jobs.values())
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a specific job by ID
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job object or None if not found
        """
        return self.jobs.get(job_id)
    
    async def start(self):
        """
        Start the job scheduler
        
        Loads jobs from configuration and starts the scheduler.
        
        Requirements: 5.3
        """
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        # Log event loop identity for verification
        loop = asyncio.get_running_loop()
        logger.info(f"Job scheduler starting on event loop: {id(loop)}")
        
        logger.info("Starting job scheduler...")
        
        # Load jobs from configuration
        job_configs = self.config_manager.get_jobs()
        for job_config in job_configs:
            job = Job(
                config=job_config,
                last_run=None,
                next_run=None,
                status='pending',
                error=None
            )
            self.jobs[job_config.job_id] = job
        
        # Start the scheduler
        self.scheduler.start()
        self._running = True
        
        # Schedule all enabled jobs
        for job in self.jobs.values():
            if job.config.enabled:
                await self._schedule_job(job)
        
        logger.info(f"Job scheduler started with {len(self.jobs)} jobs")
    
    async def stop(self):
        """
        Stop the job scheduler
        
        Gracefully shuts down the scheduler and saves state.
        """
        if not self._running:
            logger.warning("Scheduler is not running")
            return
        
        logger.info("Stopping job scheduler...")
        
        # Shutdown the scheduler
        self.scheduler.shutdown(wait=True)
        self._running = False
        
        logger.info("Job scheduler stopped")
    
    async def _schedule_job(self, job: Job):
        """
        Schedule a job with APScheduler
        
        Args:
            job: Job object to schedule
        """
        # Create interval trigger
        trigger = IntervalTrigger(hours=job.config.schedule_interval)
        
        # Add job to scheduler
        ap_job = self.scheduler.add_job(
            func=self._execute_job,
            trigger=trigger,
            args=[job],
            id=job.config.job_id,
            name=f"{job.config.job_type}_{job.config.job_id}",
            replace_existing=True
        )
        
        # Update next run time
        if ap_job.next_run_time:
            job.next_run = ap_job.next_run_time.timestamp()
        
        logger.info(
            f"Scheduled job {job.config.job_id} to run every "
            f"{job.config.schedule_interval} hours"
        )
    
    def _unschedule_job(self, job_id: str):
        """
        Remove a job from the scheduler
        
        Args:
            job_id: Job identifier
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Unscheduled job: {job_id}")
        except Exception as e:
            logger.warning(f"Failed to unschedule job {job_id}: {e}")
    
    async def _execute_job(self, job: Job):
        """
        Execute a job and handle errors
        
        Args:
            job: Job object to execute
            
        Requirements: 5.3, 5.5, 10.5
        """
        job_id = job.config.job_id
        job_type = job.config.job_type
        
        logger.info(f"Executing job: {job_id} ({job_type})")
        
        # Update status
        job.status = 'running'
        job.error = None
        
        try:
            # Get handler for job type
            handler = self.job_handlers.get(job_type)
            if not handler:
                raise ValueError(f"No handler registered for job type: {job_type}")
            
            # Execute the handler
            await handler(job.config)
            
            # Update status on success
            job.status = 'completed'
            job.last_run = datetime.now().timestamp()
            job.error = None
            
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            # Update status on failure
            job.status = 'failed'
            job.last_run = datetime.now().timestamp()
            job.error = str(e)
            
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        
        finally:
            # Update next run time
            if self._running:
                ap_job = self.scheduler.get_job(job_id)
                if ap_job and ap_job.next_run_time:
                    job.next_run = ap_job.next_run_time.timestamp()


class JobSchedulerCLI:
    """CLI interface for job management"""
    
    def __init__(self, scheduler: JobScheduler, console: Optional[Console] = None):
        """
        Initialize Job Scheduler CLI
        
        Args:
            scheduler: JobScheduler instance
            console: Optional Rich Console instance
        """
        self.scheduler = scheduler
        self.console = console or Console()
        self.ui = UIComponents(self.console)
    
    async def list_jobs(self):
        """
        Display all jobs in a formatted table
        
        Shows job ID, type, schedule, status, last run, and next run.
        
        Requirements: 5.2, 5.4
        """
        self.console.print("\n[bold cyan]═══ Scheduled Jobs ═══[/bold cyan]\n")
        
        jobs = self.scheduler.list_jobs()
        
        if not jobs:
            self.ui.show_info("No scheduled jobs")
            return
        
        # Prepare table data
        rows = []
        for job in jobs:
            # Format last run time
            if job.last_run:
                last_run = datetime.fromtimestamp(job.last_run).strftime("%Y-%m-%d %H:%M")
            else:
                last_run = "Never"
            
            # Format next run time
            if job.next_run:
                next_run = datetime.fromtimestamp(job.next_run).strftime("%Y-%m-%d %H:%M")
            else:
                next_run = "Not scheduled"
            
            # Format status with color
            status = job.status
            if status == 'completed':
                status = f"[green]{status}[/green]"
            elif status == 'failed':
                status = f"[red]{status}[/red]"
            elif status == 'running':
                status = f"[yellow]{status}[/yellow]"
            
            # Format enabled status
            enabled = "✓" if job.config.enabled else "✗"
            
            rows.append([
                job.config.job_id[:12],  # Truncate long IDs
                job.config.job_type,
                f"{job.config.schedule_interval}h",
                enabled,
                status,
                last_run,
                next_run
            ])
        
        # Display table
        self.ui.display_table(
            "Scheduled Jobs",
            ["Job ID", "Type", "Interval", "Enabled", "Status", "Last Run", "Next Run"],
            rows
        )
    
    async def create_job(self):
        """
        Create a new job with interactive prompts
        
        Prompts for job type, schedule interval, target channel, and parameters.
        
        Requirements: 5.1, 5.2, 10.1
        """
        self.console.print("\n[bold cyan]═══ Create New Job ═══[/bold cyan]\n")
        
        # Prompt for job type
        job_types = list(self.scheduler.job_handlers.keys())
        if not job_types:
            self.ui.show_error("No job handlers registered")
            return
        
        job_type = await self.ui.prompt_choice_async(
            "Select job type:",
            job_types
        )
        
        # Prompt for schedule interval
        interval_str = await self.ui.prompt_input_async(
            "Schedule interval in hours (1-168)",
            default="12"
        )
        
        try:
            schedule_interval = int(interval_str)
            if schedule_interval < 1 or schedule_interval > 168:
                self.ui.show_error("Interval must be between 1 and 168 hours")
                return
        except ValueError:
            self.ui.show_error("Invalid interval")
            return
        
        # Prompt for target channel (if applicable)
        target_channel = None
        if 'scrape' in job_type or 'channel' in job_type:
            target_channel = await self.ui.prompt_input_async(
                "Target channel (username, ID, or invite link)",
                default=None
            )
        
        # Prompt for additional parameters based on job type
        parameters = {}
        
        if 'scrape_links' in job_type:
            days_back_str = await self.ui.prompt_input_async(
                "Days back to scrape",
                default="1"
            )
            try:
                parameters['days_back'] = int(days_back_str)
            except ValueError:
                parameters['days_back'] = 1
            
            parameters['output_dir'] = await self.ui.prompt_input_async(
                "Output directory",
                default="data/links"
            )
        
        elif 'scrape_members' in job_type:
            max_members_str = await self.ui.prompt_input_async(
                "Maximum members to scrape",
                default="10000"
            )
            try:
                parameters['max_members'] = int(max_members_str)
            except ValueError:
                parameters['max_members'] = 10000
            
            parameters['fallback_to_messages'] = await self.ui.prompt_confirm_async(
                "Fallback to message-based scraping?",
                default=True
            )
        
        elif 'scrape_messages' in job_type:
            days_back_str = await self.ui.prompt_input_async(
                "Days back to scrape",
                default="7"
            )
            try:
                parameters['days_back'] = int(days_back_str)
            except ValueError:
                parameters['days_back'] = 7
            
            limit_str = await self.ui.prompt_input_async(
                "Message limit (0 for unlimited)",
                default="1000"
            )
            try:
                parameters['limit'] = int(limit_str)
            except ValueError:
                parameters['limit'] = 1000
        
        # Generate job ID
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        
        # Create job config
        job_config = JobConfig(
            job_id=job_id,
            job_type=job_type,
            schedule_interval=schedule_interval,
            target_channel=target_channel,
            parameters=parameters,
            enabled=True
        )
        
        # Create the job
        try:
            await self.scheduler.create_job(job_config)
            self.ui.show_success(f"Job created: {job_id}")
            self.console.print(f"[bold]Type:[/bold] {job_type}")
            self.console.print(f"[bold]Interval:[/bold] Every {schedule_interval} hours")
            if target_channel:
                self.console.print(f"[bold]Target:[/bold] {target_channel}")
        except Exception as e:
            self.ui.show_error(f"Failed to create job: {e}")
    
    async def edit_job(self, job_id: Optional[str] = None):
        """
        Edit job configuration
        
        Args:
            job_id: Optional job ID to edit (prompts if not provided)
            
        Requirements: 5.2, 5.4
        """
        self.console.print("\n[bold cyan]═══ Edit Job ═══[/bold cyan]\n")
        
        # Get job ID if not provided
        if not job_id:
            jobs = self.scheduler.list_jobs()
            if not jobs:
                self.ui.show_info("No jobs to edit")
                return
            
            job_choices = [f"{j.config.job_id} ({j.config.job_type})" for j in jobs]
            choice = await self.ui.prompt_choice_async("Select job to edit:", job_choices)
            job_id = choice.split()[0]
        
        # Get the job
        job = self.scheduler.get_job(job_id)
        if not job:
            self.ui.show_error(f"Job {job_id} not found")
            return
        
        # Display current configuration
        self.console.print(f"\n[bold]Current Configuration:[/bold]")
        self.console.print(f"  Job ID: {job.config.job_id}")
        self.console.print(f"  Type: {job.config.job_type}")
        self.console.print(f"  Interval: {job.config.schedule_interval} hours")
        self.console.print(f"  Enabled: {job.config.enabled}")
        if job.config.target_channel:
            self.console.print(f"  Target: {job.config.target_channel}")
        
        # Prompt for new values
        self.console.print("\n[dim]Press Enter to keep current value[/dim]\n")
        
        # Schedule interval
        interval_str = await self.ui.prompt_input_async(
            "Schedule interval in hours (1-168)",
            default=str(job.config.schedule_interval)
        )
        
        try:
            schedule_interval = int(interval_str)
            if schedule_interval < 1 or schedule_interval > 168:
                self.ui.show_error("Interval must be between 1 and 168 hours")
                return
        except ValueError:
            schedule_interval = job.config.schedule_interval
        
        # Enabled status
        enabled = await self.ui.prompt_confirm_async(
            "Enable job?",
            default=job.config.enabled
        )
        
        # Update job config
        job.config.schedule_interval = schedule_interval
        job.config.enabled = enabled
        
        # Update the job
        try:
            await self.scheduler.update_job(job.config)
            self.ui.show_success(f"Job {job_id} updated")
        except Exception as e:
            self.ui.show_error(f"Failed to update job: {e}")
    
    async def delete_job(self, job_id: Optional[str] = None):
        """
        Delete a job with confirmation
        
        Args:
            job_id: Optional job ID to delete (prompts if not provided)
            
        Requirements: 5.2, 5.4
        """
        self.console.print("\n[bold cyan]═══ Delete Job ═══[/bold cyan]\n")
        
        # Get job ID if not provided
        if not job_id:
            jobs = self.scheduler.list_jobs()
            if not jobs:
                self.ui.show_info("No jobs to delete")
                return
            
            job_choices = [f"{j.config.job_id} ({j.config.job_type})" for j in jobs]
            choice = await self.ui.prompt_choice_async("Select job to delete:", job_choices)
            job_id = choice.split()[0]
        
        # Get the job
        job = self.scheduler.get_job(job_id)
        if not job:
            self.ui.show_error(f"Job {job_id} not found")
            return
        
        # Confirm deletion
        self.console.print(f"\n[bold]Job to delete:[/bold]")
        self.console.print(f"  ID: {job.config.job_id}")
        self.console.print(f"  Type: {job.config.job_type}")
        self.console.print(f"  Interval: {job.config.schedule_interval} hours")
        
        if not await self.ui.prompt_confirm_async("\nAre you sure you want to delete this job?", default=False):
            self.ui.show_info("Deletion cancelled")
            return
        
        # Delete the job
        try:
            await self.scheduler.delete_job(job_id)
            self.ui.show_success(f"Job {job_id} deleted")
        except Exception as e:
            self.ui.show_error(f"Failed to delete job: {e}")
    
    async def run_job(self, job_id: Optional[str] = None):
        """
        Run a job immediately
        
        Args:
            job_id: Optional job ID to run (prompts if not provided)
            
        Requirements: 5.2, 5.5
        """
        self.console.print("\n[bold cyan]═══ Run Job Now ═══[/bold cyan]\n")
        
        # Get job ID if not provided
        if not job_id:
            jobs = self.scheduler.list_jobs()
            if not jobs:
                self.ui.show_info("No jobs to run")
                return
            
            job_choices = [f"{j.config.job_id} ({j.config.job_type})" for j in jobs]
            choice = await self.ui.prompt_choice_async("Select job to run:", job_choices)
            job_id = choice.split()[0]
        
        # Get the job
        job = self.scheduler.get_job(job_id)
        if not job:
            self.ui.show_error(f"Job {job_id} not found")
            return
        
        # Run the job
        self.ui.show_info(f"Running job {job_id}...")
        
        try:
            await self.scheduler.run_job_now(job_id)
            
            # Check result
            if job.status == 'completed':
                self.ui.show_success(f"Job {job_id} completed successfully")
            elif job.status == 'failed':
                self.ui.show_error(f"Job {job_id} failed: {job.error}")
            else:
                self.ui.show_info(f"Job {job_id} status: {job.status}")
                
        except Exception as e:
            self.ui.show_error(f"Failed to run job: {e}")
    
    async def show_menu(self):
        """
        Display job management menu and handle user selection
        
        Requirements: 7.2, 7.3
        """
        while True:
            self.console.print("\n[bold cyan]═══ Job Management ═══[/bold cyan]\n")
            
            choices = [
                "List Jobs",
                "Create Job",
                "Edit Job",
                "Delete Job",
                "Run Job Now",
                "Back to Main Menu"
            ]
            
            try:
                choice = await self.ui.prompt_choice_async("Select an option:", choices)
                
                if choice == "List Jobs":
                    await self.list_jobs()
                
                elif choice == "Create Job":
                    await self.create_job()
                
                elif choice == "Edit Job":
                    await self.edit_job()
                
                elif choice == "Delete Job":
                    await self.delete_job()
                
                elif choice == "Run Job Now":
                    await self.run_job()
                
                elif choice == "Back to Main Menu":
                    break
                
            except KeyboardInterrupt:
                self.console.print("\n")
                break
            except Exception as e:
                self.ui.show_error(f"An error occurred: {e}")
                import traceback
                traceback.print_exc()
