"""Abstract animation base classes.

This module defines the abstract interfaces for animation systems that can be
implemented by any rendering backend.

References:
----------

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IAnimationController(ABC):
    """Abstract interface for animation controllers.

    Controllers animate node properties by interpolating between keyframes.

    References:
    ----------

    """

    @abstractmethod
    def get_value_at_time(self, time: float) -> Any:
        """Get the interpolated value at a specific time.

        Args:
        ----
            time: Time in seconds

        Returns:
        -------
            Interpolated value at the given time

        References:
        ----------
        Observed retail KotOR I and KotOR II behavior.


        """
        ...

    @abstractmethod
    def apply(self, node: Any, value: Any) -> None:
        """Apply animated value to a node.

        Args:
        ----
            node: Backend-specific node object
            value: Animated value to apply

        References:
        ----------

        """
        ...


class IAnimationState(ABC):
    """Abstract interface for animation playback state.

    References:
    ----------

    """

    @abstractmethod
    def update(self, dt: float) -> bool:
        """Update animation state for the current frame.

        Args:
        ----
            dt: Delta time since last update (seconds)

        Returns:
        -------
            True if animation is still playing, False if finished

        References:
        ----------
        Observed retail KotOR I and KotOR II behavior.


        """
        ...

    @abstractmethod
    def play(self) -> None:
        """Start playing the animation."""
        ...

    @abstractmethod
    def pause(self) -> None:
        """Pause the animation."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop and reset the animation."""
        ...


class IAnimationManager(ABC):
    """Abstract interface for managing animations on a model.

    References:
    ----------

    """

    @abstractmethod
    def play_animation(self, animation_name: str, loop: bool = True, speed: float = 1.0) -> bool:
        """Play an animation by name.

        Args:
        ----
            animation_name: Name of the animation to play
            loop: Whether to loop the animation
            speed: Playback speed multiplier

        Returns:
        -------
            True if animation was found and started, False otherwise

        References:
        ----------
        Observed retail KotOR I and KotOR II behavior.


        """
        ...

    @abstractmethod
    def pause_animation(self) -> None:
        """Pause the current animation."""
        ...

    @abstractmethod
    def stop_animation(self) -> None:
        """Stop the current animation."""
        ...

    @abstractmethod
    def update(self, dt: float) -> None:
        """Update animation for the current frame.

        Args:
        ----
            dt: Delta time since last update (seconds)

        References:
        ----------
        Observed retail KotOR I and KotOR II behavior.


        """
        ...

    @abstractmethod
    def get_animation_names(self) -> list[str]:
        """Get list of all available animation names.

        Returns:
        -------
            List of animation names
        """
        ...

    @abstractmethod
    def has_animation(self, name: str) -> bool:
        """Check if an animation exists.

        Args:
        ----
            name: Animation name to check

        Returns:
        -------
            True if animation exists, False otherwise
        """
        ...
